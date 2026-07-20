const MAX_PAGE_BYTES = 2_000_000;
const MAX_DATASET_BYTES = 10_000_000;
const MAX_SIGNAL_RECORDS = 20_000;
const MAX_CACHED_PAGES = 4;
const HISTORY_STATE_KEY = "marksignalPagination";

const pageCache = new Map();
const configuredFeeds = new WeakSet();
let pendingNavigation;
let scrollUpdateFrame;
let instantScrollResetFrame;
let signalDatasetPromise;

const SIGNAL_REASON_LABELS = {
  filing_cluster: "Filing Cluster",
  long_filing_gap: "Long Filing Gap",
  new_class: "New Class",
  novel_tokens: "Novel Tokens",
};

const formatLabel = (value) => SIGNAL_REASON_LABELS[value]
  ?? String(value).replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());

const formatSignalDate = (value) => {
  if (!value) return "Not published";
  const date = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return "Not published";
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
};

const createElement = (tagName, className, textContent) => {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (textContent !== undefined) node.textContent = textContent;
  return node;
};

const requireString = (value, name, maximumLength) => {
  if (typeof value !== "string" || value.length > maximumLength) {
    throw new Error(`signal dataset contains an invalid ${name}`);
  }
  return value;
};

export const normaliseSignalRecord = (value) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("signal dataset contains a non-object record");
  }

  const trademarkNumber = requireString(value.trademark_number, "trade mark number", 12);
  const applicantId = requireString(value.applicant_id, "applicant ID", 100);
  if (!/^\d{1,12}$/.test(trademarkNumber) || !/^[a-z0-9-]{1,100}$/.test(applicantId)) {
    throw new Error("signal dataset contains an unsafe record identifier");
  }
  if (!Array.isArray(value.classes) || value.classes.length > 45) {
    throw new Error("signal dataset contains invalid Nice classes");
  }
  const classes = value.classes.map((classNumber) => {
    if (!Number.isInteger(classNumber) || classNumber < 1 || classNumber > 45) {
      throw new Error("signal dataset contains an invalid Nice class");
    }
    return classNumber;
  });
  if (!Array.isArray(value.reasons) || value.reasons.length > 4) {
    throw new Error("signal dataset contains invalid reasons");
  }
  const reasons = value.reasons.map((reason) => {
    if (!reason || typeof reason !== "object" || Array.isArray(reason)) {
      throw new Error("signal dataset contains an invalid reason");
    }
    const type = requireString(reason.type, "reason type", 50);
    const points = Number(reason.points);
    if (!(type in SIGNAL_REASON_LABELS) || !Number.isSafeInteger(points) || points < 0 || points > 100) {
      throw new Error("signal dataset contains an unsupported reason");
    }
    return {
      type,
      points,
      explanation: requireString(reason.explanation, "reason explanation", 2_000),
    };
  });
  const score = Number(value.score);
  const maximumScore = Number(value.maximum_score);
  if (
    !Number.isSafeInteger(score) || score < 0 || score > 100 ||
    !Number.isSafeInteger(maximumScore) || maximumScore < 1 || maximumScore > 100
  ) {
    throw new Error("signal dataset contains an invalid score");
  }
  const filingDate = value.filing_date === null
    ? null
    : requireString(value.filing_date, "filing date", 40);

  return {
    trademark_number: trademarkNumber,
    applicant_id: applicantId,
    applicant_name: requireString(value.applicant_name, "applicant name", 500),
    mark_text: requireString(value.mark_text, "mark text", 1_000),
    filing_date: filingDate,
    score,
    maximum_score: maximumScore,
    status: requireString(value.status, "status", 100),
    classes,
    reasons,
  };
};

const createSignalCard = (signal, basePath) => {
  const card = createElement("article", "signal-card");
  card.dataset.signal = "";
  card.dataset.search = [
    signal.mark_text,
    signal.applicant_name,
    signal.trademark_number,
    ...signal.reasons.map((reason) => reason.explanation),
  ].join(" ").toLocaleLowerCase("en-AU");
  card.dataset.applicant = signal.applicant_id;
  card.dataset.reasons = signal.reasons.map((reason) => reason.type).join(",");
  card.dataset.score = String(signal.score);

  const topline = createElement("div", "signal-card__topline");
  const score = createElement("span", "signal-score");
  score.setAttribute("aria-label", `Signal score ${signal.score} out of ${signal.maximum_score}`);
  score.append(createElement("b", "", String(signal.score)), createElement("small", "", `/${signal.maximum_score}`));
  const heading = createElement("div");
  heading.append(createElement("p", "signal-kicker", `Filing signal · ${formatSignalDate(signal.filing_date)}`));
  const title = createElement("h3");
  const titleLink = createElement("a", "", signal.mark_text);
  titleLink.href = `${basePath}trademarks/${signal.trademark_number}/`;
  title.append(titleLink);
  const applicantLink = createElement("a", "applicant-link", signal.applicant_name);
  applicantLink.href = `${basePath}applicants/${signal.applicant_id}/`;
  heading.append(title, applicantLink);
  topline.append(score, heading);

  const classRow = createElement("div", "class-row");
  classRow.setAttribute("aria-label", "Nice classes");
  signal.classes.forEach((classNumber) => classRow.append(createElement("span", "", `Class ${classNumber}`)));
  classRow.append(createElement("span", "status-pill", formatLabel(signal.status)));

  const reasonList = createElement("ul", "reason-list");
  signal.reasons.forEach((reason) => {
    const item = createElement("li");
    const icon = createElement("span", `reason-icon reason-icon--${reason.type}`);
    icon.setAttribute("aria-hidden", "true");
    const description = createElement("div");
    description.append(
      createElement("strong", "", formatLabel(reason.type)),
      createElement("p", "", reason.explanation),
    );
    item.append(icon, description, createElement("b", "", `+${reason.points}`));
    reasonList.append(item);
  });

  const footer = createElement("div", "signal-card__footer");
  const evidenceLink = createElement("a", "", "Evidence JSON ↓");
  evidenceLink.href = `${basePath}evidence/${signal.trademark_number}.json`;
  footer.append(createElement("span", "", `TM ${signal.trademark_number}`), evidenceLink);
  card.append(topline, classRow, reasonList, footer);
  return card;
};

const normaliseBasePath = (basePath) => {
  const path = String(basePath || "/");
  const withLeadingSlash = path.startsWith("/") ? path : `/${path}`;
  return withLeadingSlash.endsWith("/") ? withLeadingSlash : `${withLeadingSlash}/`;
};

export const getPaginationDestination = (destination, origin, basePath) => {
  let url;
  try {
    url = new URL(destination, origin);
  } catch {
    return null;
  }

  if (
    url.origin !== origin ||
    url.username ||
    url.password ||
    url.search
  ) {
    return null;
  }

  const base = normaliseBasePath(basePath);
  if (url.pathname === base) return { kind: "signals", key: "", page: 1 };

  const pagePrefix = `${base}signals/`;
  if (url.pathname.startsWith(pagePrefix)) {
    const match = url.pathname.slice(pagePrefix.length).match(/^([1-9]\d*)\/$/);
    const page = Number(match?.[1]);
    return Number.isSafeInteger(page) ? { kind: "signals", key: "", page } : null;
  }

  const applicantPrefix = `${base}applicants/`;
  if (url.pathname.startsWith(applicantPrefix)) {
    const path = url.pathname.slice(applicantPrefix.length);
    const firstPage = path.match(/^([a-z0-9-]{1,100})\/$/);
    if (firstPage) return { kind: "applicant-filings", key: firstPage[1], page: 1 };
    const numberedPage = path.match(/^([a-z0-9-]{1,100})\/filings\/([1-9]\d*)\/$/);
    const page = Number(numberedPage?.[2]);
    return numberedPage && Number.isSafeInteger(page)
      ? { kind: "applicant-filings", key: numberedPage[1], page }
      : null;
  }

  const trademarkPrefix = `${base}trademarks/`;
  if (url.pathname.startsWith(trademarkPrefix)) {
    const path = url.pathname.slice(trademarkPrefix.length);
    const firstPage = path.match(/^(\d{1,12})\/$/);
    if (firstPage) return { kind: "trademark-events", key: firstPage[1], page: 1 };
    const numberedPage = path.match(/^(\d{1,12})\/events\/([1-9]\d*)\/$/);
    const page = Number(numberedPage?.[2]);
    return numberedPage && Number.isSafeInteger(page)
      ? { kind: "trademark-events", key: numberedPage[1], page }
      : null;
  }

  return null;
};

export const getSignalPageNumber = (destination, origin, basePath) => {
  const target = getPaginationDestination(destination, origin, basePath);
  return target?.kind === "signals" ? target.page : null;
};

export const readBoundedResponseText = async (response, maximumBytes = MAX_PAGE_BYTES) => {
  const declaredLength = Number(response.headers.get("Content-Length") ?? 0);
  if (declaredLength > maximumBytes) {
    throw new Error("pagination response exceeds the declared size limit");
  }

  if (!response.body) {
    const text = await response.text();
    if (new TextEncoder().encode(text).byteLength > maximumBytes) {
      throw new Error("pagination response exceeds the size limit");
    }
    return text;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let receivedBytes = 0;
  let text = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    receivedBytes += value.byteLength;
    if (receivedBytes > maximumBytes) {
      await reader.cancel();
      throw new Error("pagination response exceeds the size limit");
    }
    text += decoder.decode(value, { stream: true });
  }

  return text + decoder.decode();
};

export const getPaginationFetchOptions = (signal) => ({
  cache: "no-store",
  credentials: "same-origin",
  headers: { Accept: "text/html" },
  redirect: "error",
  signal,
});

const loadSignalDataset = async (feed) => {
  if (signalDatasetPromise) return signalDatasetPromise;

  signalDatasetPromise = (async () => {
    const basePath = normaliseBasePath(document.body.dataset.siteBase ?? "/");
    const datasetUrl = new URL(feed.dataset.datasetUrl ?? "", window.location.origin);
    if (
      datasetUrl.origin !== window.location.origin ||
      datasetUrl.username ||
      datasetUrl.password ||
      datasetUrl.search ||
      datasetUrl.hash ||
      datasetUrl.pathname !== `${basePath}data/signals.json`
    ) {
      throw new Error("signal dataset URL is outside the expected public path");
    }

    const response = await fetch(datasetUrl, {
      cache: "no-store",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      redirect: "error",
    });
    if (
      !response.ok ||
      !response.headers.get("Content-Type")?.toLowerCase().includes("application/json") ||
      response.redirected ||
      (response.url && new URL(response.url).href !== datasetUrl.href)
    ) {
      throw new Error("signal dataset is not an available same-origin JSON resource");
    }

    const parsed = JSON.parse(await readBoundedResponseText(response, MAX_DATASET_BYTES));
    if (!Array.isArray(parsed) || parsed.length > MAX_SIGNAL_RECORDS) {
      throw new Error("signal dataset exceeds the record limit");
    }
    return parsed.map(normaliseSignalRecord);
  })().catch((error) => {
    signalDatasetPromise = undefined;
    throw error;
  });
  return signalDatasetPromise;
};

const getClientPaginationItems = (currentPage, totalPages) => {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }
  const included = new Set([1, totalPages]);
  for (let page = currentPage - 2; page <= currentPage + 2; page += 1) {
    if (page > 1 && page < totalPages) included.add(page);
  }
  const sorted = [...included].sort((left, right) => left - right);
  const items = [];
  sorted.forEach((page, index) => {
    const previous = sorted[index - 1];
    if (previous !== undefined && page - previous > 1) items.push(null);
    items.push(page);
  });
  return items;
};

const createFilteredPagerChildren = (currentPage, totalPages) => {
  const previous = currentPage > 1
    ? createElement("button", "signal-pagination__step")
    : createElement("span", "signal-pagination__step");
  if (previous instanceof HTMLButtonElement) {
    previous.type = "button";
    previous.dataset.filterPage = String(currentPage - 1);
  } else {
    previous.setAttribute("aria-disabled", "true");
  }
  const previousArrow = createElement("span", "", "←");
  previousArrow.setAttribute("aria-hidden", "true");
  previous.append(previousArrow, createElement("span", "signal-pagination__step-label", "Previous"));

  const pages = createElement("ol", "signal-pagination__pages");
  getClientPaginationItems(currentPage, totalPages).forEach((page) => {
    const item = createElement("li", page === currentPage ? "is-current" : "");
    if (page === null) {
      item.className = "signal-pagination__ellipsis";
      item.setAttribute("aria-hidden", "true");
      item.textContent = "…";
    } else if (page === currentPage) {
      const current = createElement("span");
      current.setAttribute("aria-current", "page");
      current.append(createElement("span", "visually-hidden", "Page "), String(page));
      item.append(current);
    } else {
      const button = createElement("button", "", String(page));
      button.type = "button";
      button.dataset.filterPage = String(page);
      button.setAttribute("aria-label", `Go to filtered page ${page}`);
      item.append(button);
    }
    pages.append(item);
  });

  const next = currentPage < totalPages
    ? createElement("button", "signal-pagination__step")
    : createElement("span", "signal-pagination__step");
  if (next instanceof HTMLButtonElement) {
    next.type = "button";
    next.dataset.filterPage = String(currentPage + 1);
  } else {
    next.setAttribute("aria-disabled", "true");
  }
  const nextArrow = createElement("span", "", "→");
  nextArrow.setAttribute("aria-hidden", "true");
  next.append(createElement("span", "signal-pagination__step-label", "Next"), nextArrow);
  return [previous, pages, next];
};

const setupSignalFeed = (root = document) => {
  const feed = root.matches?.("[data-signal-feed]")
    ? root
    : root.querySelector?.("[data-signal-feed]");
  if (!(feed instanceof HTMLElement) || configuredFeeds.has(feed)) return;
  configuredFeeds.add(feed);

  const form = feed.querySelector("[data-filters]");
  const list = feed.querySelector("[data-signal-list]");
  if (!(list instanceof HTMLElement)) return;
  const initialCards = Array.from(list.children).map((card) => card.cloneNode(true));
  const initialPage = Number(feed.dataset.currentPage ?? 1);
  const initialTotalPages = Number(feed.dataset.totalPages ?? 1);
  const totalSignals = Number(feed.dataset.totalSignals ?? initialCards.length);
  const pageSize = Number(feed.dataset.pageSize ?? 50);
  const count = feed.querySelector("[data-result-count]");
  const pageSummary = feed.querySelector("[data-result-page]");
  const empty = feed.querySelector("[data-empty]");
  const download = feed.querySelector("[data-download-filtered]");
  const filterStatus = feed.querySelector("[data-filter-status]");
  const pagers = Array.from(feed.querySelectorAll('[data-pagination-kind="signals"]'));
  const originalPagerChildren = pagers.map((pager) =>
    Array.from(pager.childNodes).map((child) => child.cloneNode(true))
  );
  const basePath = normaliseBasePath(document.body.dataset.siteBase ?? "/");
  let filterRevision = 0;
  let matches = [];
  let currentFilteredPage = 1;

  const currentValues = () => {
    const values = form instanceof HTMLFormElement ? new FormData(form) : new FormData();
    return {
      query: String(values.get("query") ?? "").trim().toLocaleLowerCase("en-AU"),
      applicant: String(values.get("applicant") ?? ""),
      reason: String(values.get("reason") ?? ""),
      score: Number(values.get("score") ?? 0),
    };
  };

  const hasActiveFilter = (values) =>
    Boolean(values.query || values.applicant || values.reason || values.score > 0);

  const filterDataset = (dataset, values) => dataset.filter((signal) => {
    const search = [
      signal.mark_text,
      signal.applicant_name,
      signal.trademark_number,
      ...signal.reasons.map((reason) => reason.explanation),
    ].join(" ").toLocaleLowerCase("en-AU");
    return (
      (!values.query || search.includes(values.query)) &&
      (!values.applicant || signal.applicant_id === values.applicant) &&
      (!values.reason || signal.reasons.some((reason) => reason.type === values.reason)) &&
      signal.score >= values.score
    );
  });

  const restoreStaticPage = () => {
    list.replaceChildren(...initialCards.map((card) => card.cloneNode(true)));
    pagers.forEach((pager, index) => {
      pager.replaceChildren(...originalPagerChildren[index].map((child) => child.cloneNode(true)));
    });
    feed.dataset.filterActive = "false";
    feed.dataset.currentPage = String(initialPage);
    if (count) count.textContent = String(totalSignals);
    if (pageSummary) {
      pageSummary.textContent = `Showing ${initialCards.length} on page ${initialPage} of ${initialTotalPages}`;
    }
    if (empty instanceof HTMLElement) empty.hidden = true;
    if (download instanceof HTMLButtonElement) download.disabled = false;
    if (filterStatus) {
      filterStatus.textContent = "Filters and the filtered CSV cover the full published signal dataset.";
    }
  };

  const renderFilteredPage = (page, sourcePager) => {
    const totalPages = Math.max(1, Math.ceil(matches.length / pageSize));
    currentFilteredPage = Math.min(Math.max(page, 1), totalPages);
    const start = (currentFilteredPage - 1) * pageSize;
    const pageSignals = matches.slice(start, start + pageSize);
    const previousTop = sourcePager?.getBoundingClientRect().top;

    list.replaceChildren(...pageSignals.map((signal) => createSignalCard(signal, basePath)));
    pagers.forEach((pager) => {
      pager.replaceChildren(...createFilteredPagerChildren(currentFilteredPage, totalPages));
    });
    feed.dataset.filterActive = "true";
    feed.dataset.currentPage = String(currentFilteredPage);
    if (count) count.textContent = String(matches.length);
    if (pageSummary) {
      pageSummary.textContent = matches.length
        ? `Showing ${start + 1} to ${start + pageSignals.length} on page ${currentFilteredPage} of ${totalPages}`
        : "No matching pages";
    }
    if (empty instanceof HTMLElement) empty.hidden = matches.length !== 0;
    if (download instanceof HTMLButtonElement) download.disabled = matches.length === 0;
    if (filterStatus) {
      filterStatus.textContent = "Filters and the filtered CSV cover the full published signal dataset.";
    }

    if (previousTop !== undefined && sourcePager) {
      withInstantScroll(() => {
        const difference = sourcePager.getBoundingClientRect().top - previousTop;
        instantScrollTo(window.scrollX, window.scrollY + difference);
      });
      const current = sourcePager.querySelector('[aria-current="page"]');
      if (current instanceof HTMLElement) {
        current.tabIndex = -1;
        current.focus({ preventScroll: true });
      }
    }
    const status = feed.querySelector("[data-pagination-status]");
    if (status) status.textContent = `Filtered page ${currentFilteredPage} loaded.`;
  };

  const applyFilters = async () => {
    const values = currentValues();
    const revision = ++filterRevision;
    if (!hasActiveFilter(values)) {
      matches = [];
      restoreStaticPage();
      return;
    }

    feed.setAttribute("aria-busy", "true");
    if (download instanceof HTMLButtonElement) download.disabled = true;
    if (filterStatus) filterStatus.textContent = "Loading the published signal dataset for filtering.";
    try {
      const dataset = await loadSignalDataset(feed);
      if (revision !== filterRevision || !feed.isConnected) return;
      matches = filterDataset(dataset, values);
      renderFilteredPage(1);
    } catch (error) {
      if (revision !== filterRevision || !feed.isConnected) return;
      restoreStaticPage();
      if (filterStatus) {
        filterStatus.textContent = "Full dataset filtering is temporarily unavailable. Static signal pages remain available.";
      }
      console.warn(
        "Full signal filtering failed.",
        error instanceof Error ? error.message : "Unknown error",
      );
    } finally {
      if (revision === filterRevision) feed.removeAttribute("aria-busy");
    }
  };

  form?.addEventListener("input", () => void applyFilters());
  form?.addEventListener("reset", () => window.setTimeout(() => void applyFilters()));
  feed.addEventListener("click", (event) => {
    const target = event.target;
    const button = target instanceof Element ? target.closest("[data-filter-page]") : null;
    if (!(button instanceof HTMLButtonElement)) return;
    const page = Number(button.dataset.filterPage);
    if (!Number.isSafeInteger(page) || page < 1) return;
    renderFilteredPage(page, button.closest('[data-pagination-kind="signals"]'));
  });
  download?.addEventListener("click", async () => {
    const values = currentValues();
    if (!hasActiveFilter(values)) {
      const anchor = document.createElement("a");
      anchor.href = `${basePath}data/signals.csv`;
      anchor.download = "signals.csv";
      anchor.click();
      return;
    }

    const neutralise = (value) => (/^\s*[=+\-@]/.test(value) ? `'${value}` : value);
    const escape = (value) => `"${neutralise(value).replaceAll('"', '""')}"`;
    const rows = matches.map((signal) => [
      signal.mark_text,
      signal.applicant_name,
      String(signal.score),
      signal.reasons.map((reason) => reason.type).join(","),
    ]);
    const csv = [
      "mark,applicant,score,reasons",
      ...rows.map((row) => row.map(escape).join(",")),
    ].join("\n");
    const url = URL.createObjectURL(new Blob([`${csv}\n`], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "marksignal-filtered-signals.csv";
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url));
  });
};

const getHistoryState = () =>
  history.state && typeof history.state === "object" ? history.state : {};

const replaceHistoryState = (extra = {}) => {
  history.replaceState(
    {
      ...getHistoryState(),
      [HISTORY_STATE_KEY]: true,
      scrollY: window.scrollY,
      ...extra,
    },
    "",
    window.location.href,
  );
};

const rememberCurrentScroll = () => {
  if (!document.querySelector("[data-pagination-view]")) return;
  replaceHistoryState();
};

const queueScrollStateUpdate = () => {
  if (scrollUpdateFrame !== undefined) return;
  scrollUpdateFrame = window.requestAnimationFrame(() => {
    scrollUpdateFrame = undefined;
    rememberCurrentScroll();
  });
};

const rememberPage = (key, html) => {
  pageCache.delete(key);
  pageCache.set(key, html);
  while (pageCache.size > MAX_CACHED_PAGES) {
    pageCache.delete(pageCache.keys().next().value);
  }
};

const parseDestinationPage = (html, expectedDestination) => {
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const main = parsed.querySelector("main#main-content");
  const view = main?.querySelector(`[data-pagination-view="${expectedDestination.kind}"]`);
  const actualPage = Number(view?.dataset.currentPage ?? 0);
  const actualKey = view?.dataset.paginationKey ?? "";
  if (
    !(main instanceof HTMLElement) ||
    actualPage !== expectedDestination.page ||
    actualKey !== expectedDestination.key
  ) {
    throw new Error("pagination response does not match the requested page");
  }

  main.querySelectorAll("script").forEach((script) => script.remove());
  return {
    main,
    title: parsed.title,
    description: parsed.querySelector('meta[name="description"]')?.getAttribute("content") ?? "",
    canonical: parsed.querySelector('link[rel="canonical"]')?.getAttribute("href") ?? "",
  };
};

const fetchDestinationPage = async (destination, expectedDestination, signal) => {
  const requestUrl = new URL(destination);
  requestUrl.hash = "";
  const cacheKey = `${requestUrl.pathname}${requestUrl.search}`;
  const cached = pageCache.get(cacheKey);
  if (cached !== undefined) return parseDestinationPage(cached, expectedDestination);

  const response = await fetch(requestUrl, getPaginationFetchOptions(signal));
  if (!response.ok || !response.headers.get("Content-Type")?.toLowerCase().includes("text/html")) {
    throw new Error("pagination response is not an available HTML page");
  }
  if (response.redirected || (response.url && new URL(response.url).origin !== destination.origin)) {
    throw new Error("pagination response crossed the site boundary");
  }

  const html = await readBoundedResponseText(response);
  rememberPage(cacheKey, html);
  return parseDestinationPage(html, expectedDestination);
};

const updatePageMetadata = (page, destination) => {
  if (page.title) document.title = page.title;

  const description = document.querySelector('meta[name="description"]');
  if (description && page.description) description.setAttribute("content", page.description);

  const canonical = document.querySelector('link[rel="canonical"]');
  if (canonical && page.canonical) {
    try {
      const canonicalUrl = new URL(page.canonical);
      if (canonicalUrl.protocol === "https:" && canonicalUrl.pathname === destination.pathname) {
        canonical.setAttribute("href", canonicalUrl.href);
      }
    } catch {
      // Keep the last verified canonical when the replacement metadata is malformed.
    }
  }
};

const withInstantScroll = (callback) => {
  const root = document.documentElement;
  if (instantScrollResetFrame !== undefined) {
    window.cancelAnimationFrame(instantScrollResetFrame);
  }
  root.classList.add("is-instant-scroll");
  window.getComputedStyle(root).scrollBehavior;
  callback();
  instantScrollResetFrame = window.requestAnimationFrame(() => {
    instantScrollResetFrame = undefined;
    document.documentElement.classList.remove("is-instant-scroll");
  });
};

const instantScrollTo = (left, top) => {
  window.scrollTo({ left, top, behavior: "instant" });
};

const swapPage = (page, options) => {
  const currentMain = document.querySelector("main#main-content");
  if (!(currentMain instanceof HTMLElement)) {
    throw new Error("current main region is missing");
  }

  const oldPagination = currentMain.querySelector(
    `[data-pagination-position="${options.paginationPosition}"]`,
  );
  const oldPaginationTop = oldPagination?.getBoundingClientRect().top;
  const nextMain = document.importNode(page.main, true);
  currentMain.replaceWith(nextMain);
  setupSignalFeed(nextMain);

  const nextPagination = nextMain.querySelector(
    `[data-pagination-position="${options.paginationPosition}"]`,
  );
  if (typeof options.restoreScrollY === "number") {
    withInstantScroll(() => instantScrollTo(window.scrollX, Math.max(0, options.restoreScrollY)));
  } else if (oldPaginationTop !== undefined && nextPagination) {
    withInstantScroll(() => {
      for (let attempt = 0; attempt < 4; attempt += 1) {
        const difference = nextPagination.getBoundingClientRect().top - oldPaginationTop;
        if (Math.abs(difference) < 0.5) break;
        const previousScrollY = window.scrollY;
        instantScrollTo(window.scrollX, previousScrollY + difference);
        if (window.scrollY === previousScrollY) break;
      }
    });
  }

  const currentPage = nextPagination?.querySelector('[aria-current="page"]');
  if (currentPage instanceof HTMLElement) {
    currentPage.tabIndex = -1;
    currentPage.focus({ preventScroll: true });
  }

  const viewSelector = `[data-pagination-view="${options.destination.kind}"][data-pagination-key="${options.destination.key}"]`;
  const status = nextMain.querySelector(viewSelector)?.querySelector("[data-pagination-status]");
  if (status) status.textContent = `Page ${options.destination.page} loaded.`;
};

const navigateToPage = async (destination, options) => {
  const basePath = document.body.dataset.siteBase ?? "/";
  const expectedDestination = getPaginationDestination(
    destination,
    window.location.origin,
    basePath,
  );
  if (expectedDestination === null) return false;

  pendingNavigation?.abort();
  const controller = new AbortController();
  pendingNavigation = controller;
  const currentView = document.querySelector(
    `[data-pagination-view="${expectedDestination.kind}"][data-pagination-key="${expectedDestination.key}"]`,
  );
  currentView?.setAttribute("aria-busy", "true");
  const currentStatus = currentView?.querySelector("[data-pagination-status]");
  if (currentStatus) currentStatus.textContent = `Loading page ${expectedDestination.page}.`;

  try {
    const page = await fetchDestinationPage(destination, expectedDestination, controller.signal);
    if (pendingNavigation !== controller) return true;

    swapPage(page, {
      destination: expectedDestination,
      paginationPosition: options.paginationPosition,
      restoreScrollY: options.restoreScrollY,
    });
    updatePageMetadata(page, destination);

    if (options.historyMode === "push") {
      history.pushState(
        {
          [HISTORY_STATE_KEY]: true,
          paginationPosition: options.paginationPosition,
          scrollY: window.scrollY,
        },
        "",
        `${destination.pathname}${destination.search}`,
      );
    } else {
      replaceHistoryState({ paginationPosition: options.paginationPosition });
    }
    return true;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return true;
    console.warn(
      "Enhanced pagination failed; using static navigation.",
      error instanceof Error ? error.message : "Unknown error",
    );
    if (options.historyMode === "push") {
      window.location.assign(destination.href);
    } else {
      window.location.reload();
    }
    return false;
  } finally {
    if (pendingNavigation === controller) pendingNavigation = undefined;
    document.querySelector(
      `[data-pagination-view="${expectedDestination.kind}"][data-pagination-key="${expectedDestination.key}"]`,
    )?.removeAttribute("aria-busy");
  }
};

const paginationClickHandler = (event) => {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  ) {
    return;
  }

  const target = event.target;
  const link = target instanceof Element ? target.closest("[data-client-pagination] a") : null;
  if (!(link instanceof HTMLAnchorElement) || link.target || link.hasAttribute("download")) return;

  const destination = new URL(link.href);
  const basePath = document.body.dataset.siteBase ?? "/";
  const expectedDestination = getPaginationDestination(
    destination,
    window.location.origin,
    basePath,
  );
  if (expectedDestination === null) return;

  const pagination = link.closest("[data-pagination-position]");
  if (
    pagination?.dataset.paginationKind !== expectedDestination.kind ||
    (pagination?.dataset.paginationKey ?? "") !== expectedDestination.key
  ) return;
  const paginationPosition = pagination?.dataset.paginationPosition === "bottom" ? "bottom" : "top";
  event.preventDefault();
  replaceHistoryState({ paginationPosition });
  void navigateToPage(destination, { historyMode: "push", paginationPosition });
};

const popStateHandler = (event) => {
  if (event.state?.[HISTORY_STATE_KEY] !== true) return;
  const destination = new URL(window.location.href);
  const basePath = document.body.dataset.siteBase ?? "/";
  if (getPaginationDestination(destination, window.location.origin, basePath) === null) return;

  const paginationPosition = event.state?.paginationPosition === "bottom" ? "bottom" : "top";
  const restoreScrollY = Number.isFinite(event.state?.scrollY) ? event.state.scrollY : undefined;
  void navigateToPage(destination, {
    historyMode: "pop",
    paginationPosition,
    restoreScrollY,
  });
};

if (typeof document !== "undefined" && typeof window !== "undefined") {
  setupSignalFeed();
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  replaceHistoryState();
  document.addEventListener("click", paginationClickHandler);
  window.addEventListener("popstate", popStateHandler);
  window.addEventListener("scroll", queueScrollStateUpdate, { passive: true });
}
