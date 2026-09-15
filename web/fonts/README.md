# Vendored font licensing

This directory contains self-hosted copies of the **ABC Areal** typeface
family (sans + mono subsets), used as the primary UI typeface.

- **Typeface:** ABC Areal (Regular / Medium / Bold, + Mono)
- **Vendor / owner:** Dinamo Typefaces GmbH (abcdinamo.com)
- **Acquired:** 2026-09-14 (delivery package
  `ABCAreal_2026-09-14-074527_mlsx`, received at 07:45)
- **Formats vendored:** WOFF2 (web-optimized). The original delivery also
  includes TTF and variable-font files; only the WOFF2 static weights
  actually referenced by `web/style.css @font-face` rules are kept here to
  keep the payload small.
- **Full license text:** see
  [`Dinamo_Licensing_Terms_ABC-Areal.pdf`](./Dinamo_Licensing_Terms_ABC-Areal.pdf)
  in this directory. That PDF is the governing document; this README is
  only a pointer and does not restate or summarize the terms.

## Notes for maintainers

- Do not regenerate or subset these files; any change should come from a
  fresh licensed delivery from Dinamo.
- Do not point users of this repo toward external font CDNs (Google Fonts,
  etc.) as an alternative — the design system intentionally serves fonts
  self-hosted, no third-party requests.
- If the license does not permit redistribution in public repos, move the
  font files to a private mirror and check deployment docs for how the
  production environment vendored them.
