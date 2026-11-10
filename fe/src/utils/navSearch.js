/**
 * Client-side nav / module search helpers.
 *
 * Keep these pure and cheap: they run over ~50 sidebar links or a small
 * module catalog already loaded in memory — never hit the network.
 */

/** Normalize a search string once per filter pass. */
export function normalizeNavQuery(query) {
  return String(query || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ');
}

/**
 * True when label/section text contains the query (substring match).
 *
 * Args:
 *   haystack: Display text (section or item label).
 *   needle: Already-normalized lowercase query (may be empty).
 *
 * Returns:
 *   boolean — true when empty needle or a match.
 */
export function navTextMatches(haystack, needle) {
  if (!needle) return true;
  return String(haystack || '')
    .toLowerCase()
    .includes(needle);
}

/**
 * Filter visible nav sections by item/section label.
 *
 * Expects sections shaped like Layout's ``visibleSections``
 * (``{ id, label, visibleItems: [{ label, to, ... }] }``).
 *
 * Args:
 *   sections: Array of permission-filtered sections (0–30 typical).
 *   query: Raw user input.
 *
 * Returns:
 *   New array of sections with ``visibleItems`` narrowed; empty query
 *   returns the same ``sections`` reference (no alloc).
 */
export function filterNavSections(sections, query) {
  const needle = normalizeNavQuery(query);
  if (!needle) return sections;
  if (!Array.isArray(sections) || sections.length === 0) return sections;

  const out = [];
  for (const section of sections) {
    const sectionHit = navTextMatches(section.label, needle);
    const items = Array.isArray(section.visibleItems) ? section.visibleItems : [];
    const visibleItems = sectionHit
      ? items
      : items.filter((item) => navTextMatches(item.label, needle));
    if (visibleItems.length === 0) continue;
    out.push(
      visibleItems === items ? section : { ...section, visibleItems }
    );
  }
  return out;
}

/**
 * Filter Module Settings catalog domains by module / feature text.
 *
 * Args:
 *   catalog: Array of ``{ id, label, description, modules: [...] }``.
 *   query: Raw user input.
 *
 * Returns:
 *   Filtered catalog (same reference when query empty).
 */
export function filterModuleCatalog(catalog, query) {
  const needle = normalizeNavQuery(query);
  if (!needle) return catalog;
  if (!Array.isArray(catalog) || catalog.length === 0) return catalog;

  const out = [];
  for (const domain of catalog) {
    const domainHit =
      navTextMatches(domain.label, needle) ||
      navTextMatches(domain.description, needle);
    const modules = Array.isArray(domain.modules) ? domain.modules : [];
    const matchedModules = [];

    for (const mod of modules) {
      if (domainHit || moduleMatchesQuery(mod, needle)) {
        matchedModules.push(mod);
      }
    }
    if (matchedModules.length === 0) continue;
    out.push(
      matchedModules === modules && domainHit
        ? domain
        : { ...domain, modules: matchedModules }
    );
  }
  return out;
}

function moduleMatchesQuery(mod, needle) {
  if (
    navTextMatches(mod.module_name_display, needle) ||
    navTextMatches(mod.module_name, needle) ||
    navTextMatches(mod.description, needle)
  ) {
    return true;
  }
  const features = mod.features || {};
  for (const feature of Object.values(features)) {
    if (
      navTextMatches(feature.feature_name, needle) ||
      navTextMatches(feature.description, needle) ||
      navTextMatches(feature.feature_key, needle)
    ) {
      return true;
    }
  }
  const children = mod.rollup_children || [];
  for (const child of children) {
    if (moduleMatchesQuery(child, needle)) return true;
  }
  return false;
}
