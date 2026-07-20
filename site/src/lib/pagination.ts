export const SIGNAL_PAGE_SIZE = 50;
export const FILING_PAGE_SIZE = 25;
export const EVENT_PAGE_SIZE = 25;

export const getPageCount = (itemCount: number, pageSize: number): number =>
  Math.max(1, Math.ceil(itemCount / pageSize));

export const getPage = <T>(items: T[], page: number, pageSize: number): T[] => {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
};

export const getSignalPageCount = (signalCount: number): number =>
  getPageCount(signalCount, SIGNAL_PAGE_SIZE);

export const getSignalPage = <T>(items: T[], page: number): T[] =>
  getPage(items, page, SIGNAL_PAGE_SIZE);

export const getPaginationItems = (
  currentPage: number,
  totalPages: number
): Array<number | null> => {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const includedPages = new Set([1, totalPages]);
  for (let page = currentPage - 2; page <= currentPage + 2; page += 1) {
    if (page > 1 && page < totalPages) includedPages.add(page);
  }

  const sortedPages = [...includedPages].sort((left, right) => left - right);
  const items: Array<number | null> = [];

  sortedPages.forEach((page, index) => {
    const previousPage = sortedPages[index - 1];
    if (previousPage !== undefined && page - previousPage > 1) items.push(null);
    items.push(page);
  });

  return items;
};

export const getSignalPaginationItems = getPaginationItems;
