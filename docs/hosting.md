# Build and host

Run locally with `npm start` after building. No hosting account or cloud CLI is
required. See the [README](../README.md) for setup.

To publish your own copy, build the static site:

```sh
npm ci
npm run build
```

Upload the contents of `dist/` to a static host of your choice. Keep its directory
structure and serve `index.html` at the site root. The project does not select a
hosting provider, account or destination for your copy.

Optional research assets are included when available locally and within the
build's size limit; missing files resolve to recorded source URLs. Source archives
remain external. See [data and downloads](data-provenance.md) for offline use and
source-specific terms. The generated `_headers` and `_redirects` files are
optional hints for compatible hosts; browser asset resolution does not depend on
them.

Check the gallery, paper details, a video and file downloads on the chosen host.
Personal deployment configuration and credentials belong outside tracked project
files. The maintainer's online demo is linked from the README and is optional.
