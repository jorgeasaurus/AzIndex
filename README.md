# Az Index — Azure PowerShell Cmdlet Reference

A fast, beautiful, static reference site for Azure PowerShell (`Az`) cmdlets — modeled after the [MgGraphIndex](https://github.com/MgGraphIndex) project.

Browse, search, and explore every `Az.*` cmdlet with instant filtering, syntax highlighting, parameter tables, copy-ready examples, and multiple visual themes — all in a single HTML file with no runtime dependencies.

---

## Screenshot

> A live screenshot will be added once the site is deployed. Run locally to see Az Index in action.

---

## Live Site

Deploy the `public/` directory to any static host (GitHub Pages, Azure Static Web Apps, Netlify, etc.).

With the included GitHub Actions workflow, data is refreshed daily from the official [azure-docs-powershell](https://github.com/MicrosoftDocs/azure-docs-powershell) repository.

---

## Themes

| Theme | File | Description |
|---|---|---|
| 🪟 Acrylic | `index.html` | Glassmorphism, Azure blue — default |
| ⚡ Cyberpunk | `cyberpunk.html` | Neon cyan/magenta, scanlines |
| 📺 CRT | `crt.html` | Green phosphor terminal |
| 🌆 Synthwave | `synthwave.html` | Purple/pink retro gradient |
| 📐 Blueprint | `blueprint.html` | Technical blueprint grid |
| ☀️ Solarized | `solarized.html` | Classic solarized dark/light |
| 🌐 Geocities | `geocities.html` | 90s web nostalgia |

---

## Using Locally

No build step required — just open in a browser via a local server (required because of `fetch()` calls):

```bash
# Python (recommended)
cd public
python -m http.server 8080
# Then open http://localhost:8080
```

Or with Node.js:

```bash
npx serve public
```

---

## Features

- **Instant search** with fuzzy matching across cmdlet names, modules, descriptions
- **Filter** by module, category, and verb
- **Sort** by name, module, verb, or category
- **Lazy loading** in chunks of 50 for performance
- **Expandable cards** with syntax, parameters table, examples, and related cmdlets
- **Copy button** on every example
- **Export** results as JSON or CSV
- **Presets** saved to `localStorage`
- **URL hash state** — bookmarkable/shareable filter states
- **Keyboard shortcuts**: `/` to search, `j`/`k` to navigate, `Enter` to expand, `Esc` to clear
- **Light/dark mode** toggle (persisted)
- **Alpha navigation** sidebar
- **Recent searches** dropdown
- **MS Learn links** on every cmdlet name

---

## Data Pipeline

```
MicrosoftDocs/azure-docs-powershell (GitHub)
        ↓  (cloned daily via GitHub Actions)
scripts/parse_docs.py
        ↓
public/data/manifest.json          ← cmdlet list + metadata
public/data/descriptions.json      ← one-line descriptions
public/data/modules/Az.*.json      ← syntax + examples per module
        ↓
GitHub Pages  →  index.html / *.html
```

The workflow (`.github/workflows/update-cmdlet-data.yml`) runs on a daily schedule and after each manual trigger:
1. Shallow-clones the docs repository
2. Runs `parse_docs.py` to extract cmdlet metadata
3. Commits any changed data files
4. Deploys `public/` to GitHub Pages

### Generating data locally (without docs repo)

If you have the Az PowerShell modules installed, you can generate the data files directly:

```powershell
# Install Az if needed
Install-Module Az -Scope CurrentUser

# Generate data files
.\scripts\get-azcmdlets.ps1
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Open a pull request

### Adding a new theme

1. Copy `public/acrylic.html` to `public/mytheme.html`
2. Replace the `:root { ... }` CSS variables with your theme colors
3. Add any theme-specific CSS overrides before `</style>`
4. Add the theme to the `<select>` dropdown in every HTML file
5. Update this README

### Improving the parser

`scripts/parse_docs.py` uses Python stdlib only — no external dependencies.
The category mapping lives in `CATEGORY_MAP` near the top of the file.

---

## License

MIT
