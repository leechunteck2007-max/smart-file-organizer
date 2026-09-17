# License recommendation

Recommendation: **MIT for the project's original source and screenshots**. The owner confirmed MIT during release preparation. LICENSE now contains the complete MIT terms; the previous private placeholder did not grant an open-source license.

| Option | Benefits | Obligations and tradeoffs |
|---|---|---|
| MIT | Short permissive license; reuse, modification and commercial distribution permitted | Keep copyright and license notices; no explicit patent grant |
| Apache 2.0 | Permissive reuse with an explicit patent grant and patent termination terms | Longer license; preserve notices and identify modifications as required |

Installed direct runtime dependencies are MIT, BSD 3-Clause, ISC or PSF licensed. TypeScript and Playwright build tools are Apache 2.0. PyInstaller is GPL with the bootloader exception, which permits distributing generated applications under the chosen application license. Electron also bundles Chromium components with their own notices; the application license does not replace those licenses. No v0 or 21st component code or third-party raster assets were copied.

No direct dependency requirement was found that forces the original application source to use a copyleft license. The release must retain the supplied Electron/Chromium and Python dependency notices. This recommendation does not relicense dependencies.

Sources: [MIT](https://choosealicense.com/licenses/mit/), [Apache 2.0](https://choosealicense.com/licenses/apache-2.0/), [PyInstaller exception](https://pyinstaller.org/en/stable/license.html). THIRD_PARTY_NOTICES.md records installed versions and redistributions.

The MIT copyright holder is **Smart File Organizer contributors**, avoiding publication of the developer's personal identity. Owner selection is resolved. Dependencies retain their own notices and redistribution terms.
