// Templater user script: tp.user.slug("Compare café options") -> "compare-cafe-options".
// Kebab-case without accents, the file-name rule of the wiki. Templater loads every .js file in the
// user scripts folder (Settings -> Templater -> User script functions: _templates/_scripts).
function slug(text) {
  return String(text)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/['’]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
module.exports = slug;
