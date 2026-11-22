// Templater user script: tp.user.slug("Compare café options") -> "compare-cafe-options".
// The file-name rule of the wiki: lower case, words joined by hyphens. Latin letters lose their
// accents (é -> e, ß -> ss, ø -> o, ł -> l); letters and digits of every other script are kept as
// they are ("Заметка о тесте" -> "заметка-о-тесте", "会議メモ" -> "会議メモ"). A title without any
// letter or digit ("???") gets the date and time as its name, so a note never ends up nameless.
// Templater loads every .js file in the user scripts folder
// (Settings -> Templater -> User script functions: _templates/_scripts).
const LATIN = { "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "đ": "d", "ð": "d", "þ": "th", "ł": "l", "ı": "i", "ħ": "h", "ŋ": "ng" };
const MAX = 80;

function stamp(now) {
  const two = (n) => String(n).padStart(2, "0");
  return now.getFullYear() + "-" + two(now.getMonth() + 1) + "-" + two(now.getDate()) + "-" +
    two(now.getHours()) + two(now.getMinutes()) + two(now.getSeconds());
}

function slug(text, now) {
  let s = String(text == null ? "" : text)
    .toLowerCase()
    .replace(/[ßæœøđðþłıħŋ]/g, (c) => LATIN[c])
    .normalize("NFD")
    .replace(/([a-z])[\u0300-\u036f]+/g, "$1")
    .normalize("NFC")
    .replace(/['\u2019\u2018]/g, "")
    .replace(/[^\p{L}\p{N}\p{M}]+/gu, "-")
    .replace(/^-+|-+$/g, "");
  const chars = Array.from(s);
  if (chars.length > MAX) {
    const cut = chars.slice(0, MAX).join("");
    s = cut.replace(/-[^-]*$/, "") || cut;
  }
  return s || stamp(now || new Date());
}
module.exports = slug;
