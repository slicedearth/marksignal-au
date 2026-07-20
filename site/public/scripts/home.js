const MAX_PAGE_BYTES = 2_000_000;
const MAX_CACHED_PAGES = 4;
const HISTORY_STATE_KEY = "marksignalSignalPage";

const pageCache = new Map();
const configuredFeeds = new WeakSet();
let pendingNavigation;
let scrollUpdateFrame;
let instantScrollResetFrame;

const normaliseBasePath = (basePath) => {
  const path = String(basePath || "/");
  const withLeadingSlash = path.startsWith("/") ? path : `/${path}`;
  return withLeadingSlash.endsWith("/") ? withLeadingSlash : `${withLeadingSlash}/`;
};

export const getSignalPageNumber = (destination, origin, basePath) => {
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
  if (url.pathname === base) return 1;

  const pagePrefix = `${base}signals/`;
  if (!url.pathname.startsWith(pagePrefix)) return null;
  const match = url.pathname.slice(pagePrefix.length).match(/^([1-9]\d*)\/$/);
  if (!match) return null;

  const page = Number(match[1]);
  return Number.isSafeInteger(page) ? page : null;
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

const setupSignalFeed = (root = document) => {
  const feed = root.matches?.("[data-signal-feed]")
    ? root
    : root.querySelector?.("[data-signal-feed]");
  if (!(feed instanceof HTMLElement) || configuredFeeds.has(feed)) return;
  configuredFeeds.add(feed);

  const form = feed.querySelector("[data-filters]");
  const cards = Array.from(feed.querySelectorAll("[data-signal]"));
  const count = feed.querySelector("[data-result-count]");
  const empty = feed.querySelector("[data-empty]");
  const download = feed.querySelector("[data-download-filtered]");

  const applyFilters = () => {
    if (!(form instanceof HTMLFormElement)) return;
    const values = new FormData(form);
    const query = String(values.get("query") ?? "").trim().toLocaleLowerCase("en-AU");
    const applicant = String(values.get("applicant") ?? "");
    const reason = String(values.get("reason") ?? "");
    const score = Number(values.get("score") ?? 0);
    let visible = 0;

    cards.forEach((card) => {
      if (!(card instanceof HTMLElement)) return;
      const matches =
        (!query || (card.dataset.search ?? "").includes(query)) &&
        (!applicant || card.dataset.applicant === applicant) &&
        (!reason || (card.dataset.reasons ?? "").split(",").includes(reason)) &&
        Number(card.dataset.score ?? 0) >= score;
      card.hidden = !matches;
      if (matches) visible += 1;
    });

    if (count) count.textContent = String(visible);
    if (empty instanceof HTMLElement) empty.hidden = visible !== 0;
    if (download instanceof HTMLButtonElement) download.disabled = visible === 0;
  };

  form?.addEventListener("input", applyFilters);
  form?.addEventListener("reset", () => window.setTimeout(applyFilters));
  download?.addEventListener("click", () => {
    const neutralise = (value) => (/^[=+\-@\t\r\n]/.test(value) ? `'${value}` : value);
    const escape = (value) => `"${neutralise(value).replaceAll('"', '""')}"`;
    const rows = cards
      .filter((card) => card instanceof HTMLElement && !card.hidden)
      .map((card) => {
        const title = card.querySelector("h3")?.textContent?.trim() ?? "";
        const applicant = card.querySelector(".applicant-link")?.textContent?.trim() ?? "";
        return [title, applicant, card.dataset.score ?? "", card.dataset.reasons ?? ""];
      });
    const csv = [
      "mark,applicant,score,reasons",
      ...rows.map((row) => row.map(escape).join(",")),
    ].join("\n");
    const url = URL.createObjectURL(new Blob([`${csv}\n`], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `marksignal-signals-page-${feed.dataset.currentPage ?? "1"}.csv`;
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
  if (!document.querySelector("[data-signal-feed]")) return;
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

const parseDestinationPage = (html, expectedPage) => {
  const parsed = new DOMParser().parseFromString(html, "text/html");
  const main = parsed.querySelector("main#main-content");
  const feed = main?.querySelector("[data-signal-feed]");
  const actualPage = Number(feed?.dataset.currentPage ?? 0);
  if (!(main instanceof HTMLElement) || actualPage !== expectedPage) {
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

const fetchDestinationPage = async (destination, expectedPage, signal) => {
  const requestUrl = new URL(destination);
  requestUrl.hash = "";
  const cacheKey = `${requestUrl.pathname}${requestUrl.search}`;
  const cached = pageCache.get(cacheKey);
  if (cached !== undefined) return parseDestinationPage(cached, expectedPage);

  const response = await fetch(requestUrl, getPaginationFetchOptions(signal));
  if (!response.ok || !response.headers.get("Content-Type")?.toLowerCase().includes("text/html")) {
    throw new Error("pagination response is not an available HTML page");
  }
  if (response.redirected || (response.url && new URL(response.url).origin !== destination.origin)) {
    throw new Error("pagination response crossed the site boundary");
  }

  const html = await readBoundedResponseText(response);
  rememberPage(cacheKey, html);
  return parseDestinationPage(html, expectedPage);
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

  const status = nextMain.querySelector("[data-pagination-status]");
  if (status) status.textContent = `Page ${options.expectedPage} loaded.`;
};

const navigateToSignalPage = async (destination, options) => {
  const basePath = document.body.dataset.siteBase ?? "/";
  const expectedPage = getSignalPageNumber(destination, window.location.origin, basePath);
  if (expectedPage === null) return false;

  pendingNavigation?.abort();
  const controller = new AbortController();
  pendingNavigation = controller;
  const currentFeed = document.querySelector("[data-signal-feed]");
  currentFeed?.setAttribute("aria-busy", "true");
  const currentStatus = currentFeed?.querySelector("[data-pagination-status]");
  if (currentStatus) currentStatus.textContent = `Loading page ${expectedPage}.`;

  try {
    const page = await fetchDestinationPage(destination, expectedPage, controller.signal);
    if (pendingNavigation !== controller) return true;

    swapPage(page, {
      expectedPage,
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
    document.querySelector("[data-signal-feed]")?.removeAttribute("aria-busy");
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
  const link = target instanceof Element ? target.closest(".signal-pagination a") : null;
  if (!(link instanceof HTMLAnchorElement) || link.target || link.hasAttribute("download")) return;

  const destination = new URL(link.href);
  const basePath = document.body.dataset.siteBase ?? "/";
  if (getSignalPageNumber(destination, window.location.origin, basePath) === null) return;

  const pagination = link.closest("[data-pagination-position]");
  const paginationPosition = pagination?.dataset.paginationPosition === "bottom" ? "bottom" : "top";
  event.preventDefault();
  replaceHistoryState({ paginationPosition });
  void navigateToSignalPage(destination, { historyMode: "push", paginationPosition });
};

const popStateHandler = (event) => {
  if (event.state?.[HISTORY_STATE_KEY] !== true) return;
  const destination = new URL(window.location.href);
  const basePath = document.body.dataset.siteBase ?? "/";
  if (getSignalPageNumber(destination, window.location.origin, basePath) === null) return;

  const paginationPosition = event.state?.paginationPosition === "bottom" ? "bottom" : "top";
  const restoreScrollY = Number.isFinite(event.state?.scrollY) ? event.state.scrollY : undefined;
  void navigateToSignalPage(destination, {
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
