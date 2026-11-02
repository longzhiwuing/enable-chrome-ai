# Enable Chrome AI ✨

Researched and scripted by [lcandy2](https://twitter.com/vanillaCitron).

[![Twitter](https://img.shields.io/twitter/follow/vanillaCitron)](https://twitter.com/vanillaCitron)


English | [中文](README.zh.md)

Enable Gemini in Chrome, AI Powered History search, and DevTools AI Innovations in Google Chrome—without cleaning data or reinstalling.

<img width="512" alt="Google Chrome Gemini in Chrome" src="https://github.com/user-attachments/assets/a88c56a7-f20b-432a-926c-0184194225b4" />

Tiny Python helper that enables Chrome's built-in AI features by patching your local profile data (`variations_country`, `variations_permanent_consistency_country`, and `is_glic_eligible`)—no browser flags required.

## ✅ Requirements
- Python `3.13+` (see `.python-version` / `pyproject.toml`)
- Google Chrome installed (Stable/Canary/Dev/Beta)

## ⚡️ Quick Start (uv)
1. Install uv (once):
   - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - macOS & Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - See [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/) for more options.
2. Install deps (creates venv automatically): `uv sync`.
3. Run the script: `uv run main.py`.
4. Chrome will close while patching; after it restarts, press Enter to finish.

## ⚡️ Quick Start (pip)
1. Create and activate a venv.
2. Install deps: `python -m pip install psutil zstandard`.
3. Run: `python main.py`.

## 🔧 What Happens
- Finds Chrome user data for Stable/Canary/Dev/Beta on Windows, macOS, and Linux.
- Kills top-level Chrome processes to avoid file locks, then brings them back.
- Sets all `is_glic_eligible` to `true` in `Local State` (recursive search).
- Sets `variations_country` to `"us"` in `Local State`.
- Sets `variations_permanent_consistency_country` to `["<version>", "us"]` in `Local State`.
- When present, patches session and permanent country fields to `"us"` in the Zstandard-compressed `VariationsSeedV2` and `VariationsSafeSeedV2` files used by newer desktop Chrome versions. Seed payloads, signatures, versions, and unknown protobuf fields are preserved.
- Validates both seed files before changing them, keeps the first original of each changed seed as `<filename>.bak`, and replaces each seed atomically. Missing seed files are skipped for older Chrome versions.
- Restarts any Chrome builds that were running before the patch.

## ⚠️ Caveats / Known Limitations
- The script expects `User Data/Local State` to exist; if it's missing, the run can fail (launch Chrome once to generate it).
- Chrome restart only happens if the executable path can be detected from running processes.
- On macOS, process detection is name-based (`Google Chrome*`) and may terminate more than just the "top-level" app process.
- On Linux, process detection expects an executable name of `chrome`; if your build uses a different name, Chrome may not be closed (and files may remain locked).
- Invalid, unsupported, or oversized seed files stop patching rather than being overwritten. To restore seed backups, fully exit Chrome and copy each `<filename>.bak` over its matching seed file. Backups are not overwritten on later runs.
- Chrome updates or newly downloaded seed data may reset the region. Google account eligibility, enterprise policies, and server-side restrictions can still prevent access.

## 🛟 Notes
- The script writes to your existing Chrome profile; back up `User Data` if you want a safety net.
- Run as the same OS user who owns the Chrome profile to ensure write access.
- Not affiliated with Google—use at your own risk.

## Verification
Run `uv run python -m unittest discover -s tests -v`. The tests use temporary profiles and never close Chrome or modify your real profile.


## 📜 License
Please credit this project when reposting or creating derivative works.

## 🙏 Acknowledgments
- [show-copilot](https://github.com/hzkaai/show-copilot)
