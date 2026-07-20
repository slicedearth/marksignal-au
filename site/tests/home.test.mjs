import assert from "node:assert/strict";
import test from "node:test";

import {
  getSignalPageNumber,
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
