# Third-party notices

Original application code is MIT licensed. This does not relicense bundled dependencies. Versions below are the pinned release inputs; the Windows ZIP includes verbatim notices in `NOTICE/`, its Python license and `LICENSES.chromium.html`.

| Component | Version | License | Purpose / redistribution |
| --- | --- | --- | --- |
| Python | 3.13 | PSF and included component terms | Frozen engine runtime. Preserve full Python LICENSE.txt, including Microsoft Distributable Code conditions. |
| python-docx | 1.2.0 | MIT | DOCX reports; notice retained. |
| pypdf | 6.19.0 | BSD-3-Clause | Local PDF text; notice retained. |
| lxml | 6.1.3 | BSD-3-Clause and included libxml2/libxslt terms | Word XML support; LICENSE and LICENSES retained. |
| typing_extensions | 4.15.0 | PSF-2.0 | Python support; notice retained. |
| Electron | 44.4.0 | MIT; bundled Chromium/component terms | Desktop runtime. Electron MIT preserved separately before application LICENSE replaces the root file. Chromium full notices retained. |
| React / React DOM | 19.3.0 | MIT | UI; notices retained. |
| Lucide React | 0.577.0 | ISC | Icons; notice retained. |
| PyInstaller | 6.16.0 | GPL-2.0-or-later with bootloader exception | Build tool/bootloader. Exception permits the generated application under its own license; COPYING retained. |
| TypeScript | 5.9.3 | Apache-2.0 | Development only. |
| Vite | 7.3.6 | MIT | Development only. |
| Playwright | 1.63.0 | Apache-2.0 | Desktop test tool, not bundled. |
| Node.js / pnpm | 24 / 11.19.0 | MIT / MIT | Development only; normal users do not need them. |

Python's complete license includes its third-party attribution and restrictions (including libffi, compression libraries and Microsoft runtime code). OpenSSL 3 uses Apache-2.0; SQLite is public domain. Their upstream notices are retained in `assets/licenses/` and copied into the package. Python/Chromium license texts contain vendor contributor names/contacts as required attribution; those are not the developer's private details.

The distribution targets Windows only. Microsoft runtime files remain subject to Microsoft's Distributable Code conditions in the Python license; do not strip those notices, use Microsoft endorsement claims, or redistribute those files for other platforms. Recipients redistributing the bundled Microsoft code must comply with the same conditions. See the included notice and [Python's license documentation](https://docs.python.org/3.13/license.html).

No external photos, copyrighted document examples, v0 component code or 21st component source are redistributed. Screenshots are generated from synthetic fixtures. Segoe UI is requested as a system font and is not redistributed.

Sources: installed package license files; [Electron licenses](https://github.com/electron/electron/blob/main/LICENSE); [PyInstaller exception](https://pyinstaller.org/en/stable/license.html); [OpenSSL license](https://www.openssl.org/source/license.html); [SQLite public domain](https://www.sqlite.org/copyright.html).
