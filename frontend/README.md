This is the frontend API bundle for X-Talk. See https://github.com/xcc-zach/xtalk for details.

## Build the package

Use `npm run build` when you want a production bundle in `dist/`. This is the command to run before publishing, packaging, or verifying the final output.

Use `npm run watch` while developing the frontend package locally. It runs webpack in watch mode and rebuilds automatically whenever files under `src/` change.

## Generate API documentation

The frontend API docs are generated with TypeDoc and `typedoc-plugin-markdown`, then written to the repository docs site so MkDocs can include them.

From the repository root:

```bash
cd frontend
npm install
npm run docs
```

The generated Markdown files are written to `../docs/api/client/`.

Only the English API docs are generated. The MkDocs i18n configuration falls back to the English page for the Chinese site.
