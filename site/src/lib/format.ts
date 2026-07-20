const dateFormatter = new Intl.DateTimeFormat("en-AU", {
  day: "numeric",
  month: "short",
  year: "numeric"
});

export function formatDate(value: string | null | undefined, includeTime = false): string {
  if (!value) return "Not published";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "Invalid date";
  if (!includeTime) return dateFormatter.format(date);
  return new Intl.DateTimeFormat("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Australia/Melbourne",
    timeZoneName: "short"
  }).format(date);
}

export function label(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

