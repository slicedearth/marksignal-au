const form = document.querySelector("[data-filters]");
const cards = Array.from(document.querySelectorAll("[data-signal]"));
const count = document.querySelector("[data-result-count]");
const empty = document.querySelector("[data-empty]");
const download = document.querySelector("[data-download-filtered]");

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
  anchor.download = "marksignal-filtered-signals.csv";
  anchor.click();
  URL.revokeObjectURL(url);
});
