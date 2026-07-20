import assert from "node:assert/strict";
import test from "node:test";

import {
  getPaginationDestination,
  getPaginationFetchOptions,
  getSignalPageNumber,
  normaliseSignalRecord,
  readBoundedResponseText,
} from "../public/scripts/home.js";

test("pagination destinations stay on the exact generated route", () => {
  const origin = "https://example.test";

  assert.equal(getSignalPageNumber("https://example.test/", origin, "/"), 1);
  assert.equal(
    getSignalPageNumber("https://example.test/signals/27/#signal-results", origin, "/"),
    27,
  );
  assert.equal(
    getSignalPageNumber(
      "https://example.test/marksignal-au/signals/3/#signal-results",
      origin,
      "/marksignal-au/",
    ),
    3,
  );

  assert.equal(
    getSignalPageNumber("https://outside.test/signals/2/", origin, "/"),
    null,
  );
  assert.equal(
    getSignalPageNumber("https://example.test/data/", origin, "/"),
    null,
  );
  assert.equal(
    getSignalPageNumber("https://example.test/signals/2/?next=3", origin, "/"),
    null,
  );
  assert.equal(
    getSignalPageNumber("https://example.test/signals/2/#local-fragment", origin, "/"),
    2,
  );
  assert.equal(
    getSignalPageNumber("https://example.test/signals/0/", origin, "/"),
    null,
  );
});

test("record history pagination stays on exact applicant and trade mark routes", () => {
  const origin = "https://example.test";

  assert.deepEqual(
    getPaginationDestination(
      "https://example.test/marksignal-au/applicants/coles-group/filings/12/#filing-history",
      origin,
      "/marksignal-au/",
    ),
    { kind: "applicant-filings", key: "coles-group", page: 12 },
  );
  assert.deepEqual(
    getPaginationDestination(
      "https://example.test/marksignal-au/trademarks/123456/events/2/#event-history",
      origin,
      "/marksignal-au/",
    ),
    { kind: "trademark-events", key: "123456", page: 2 },
  );
  assert.deepEqual(
    getPaginationDestination(
      "https://example.test/marksignal-au/applicants/xero/",
      origin,
      "/marksignal-au/",
    ),
    { kind: "applicant-filings", key: "xero", page: 1 },
  );
  assert.equal(
    getPaginationDestination(
      "https://example.test/marksignal-au/applicants/../data/filings/2/",
      origin,
      "/marksignal-au/",
    ),
    null,
  );
  assert.equal(
    getPaginationDestination(
      "https://example.test/marksignal-au/trademarks/123/events/2/?next=3",
      origin,
      "/marksignal-au/",
    ),
    null,
  );
});

test("bounded page reads accept small HTML and reject oversized bodies", async () => {
  const accepted = new Response("<main>safe</main>", {
    headers: { "Content-Type": "text/html" },
  });
  assert.equal(await readBoundedResponseText(accepted, 100), "<main>safe</main>");

  const declaredOversize = new Response("short", {
    headers: { "Content-Length": "101" },
  });
  await assert.rejects(
    readBoundedResponseText(declaredOversize, 100),
    /declared size limit/,
  );

  const streamedOversize = new Response("x".repeat(101));
  await assert.rejects(readBoundedResponseText(streamedOversize, 100), /size limit/);
});

test("pagination requests bypass stale browser documents", () => {
  const controller = new AbortController();
  const options = getPaginationFetchOptions(controller.signal);

  assert.equal(options.cache, "no-store");
  assert.equal(options.credentials, "same-origin");
  assert.equal(options.redirect, "error");
  assert.deepEqual(options.headers, { Accept: "text/html" });
  assert.equal(options.signal, controller.signal);
});

test("client-side signal records are validated before rendering", () => {
  const valid = {
    trademark_number: "1234567",
    applicant_id: "example-limited",
    applicant_name: "Example Limited",
    mark_text: "EXAMPLE MARK",
    filing_date: "2026-07-20",
    score: 45,
    maximum_score: 90,
    status: "accepted",
    classes: [9, 42],
    reasons: [
      {
        type: "new_class",
        points: 25,
        explanation: "First observed filing in class 42.",
      },
    ],
  };

  assert.deepEqual(normaliseSignalRecord(valid), valid);
  assert.throws(
    () => normaliseSignalRecord({ ...valid, applicant_id: "../outside" }),
    /unsafe record identifier/,
  );
  assert.throws(
    () => normaliseSignalRecord({ ...valid, classes: [46] }),
    /invalid Nice class/,
  );
  assert.throws(
    () => normaliseSignalRecord({ ...valid, reasons: [{ ...valid.reasons[0], type: "unknown" }] }),
    /unsupported reason/,
  );
});
