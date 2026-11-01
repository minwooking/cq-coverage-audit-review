# OpenTimestamps record (prereg manifest)

Stamped (UTC): 2026-10-20T22:35:54Z (= 2026-10-21 07:35 KST), client opentimestamps-client 0.7.2.
Only SHA256 digests were sent to the public calendars; no file content left the machine.

- PREREG_MANIFEST.json sha256 = 007a46f014189a36e338649aa67ab8196e6825849e68d06e25cd9d7ef1738a16 (equals MANIFEST_SHA256 in PREREG_MANIFEST.md)
- Tagged commit access2026-prereg-manifest-2026-10-21 = 02ebb7645c1d6545a688acbe528ccb7a24dee84e (PREREG_MANIFEST_COMMIT.txt)

Calendars used (both stamps): a.pool.opentimestamps.org, b.pool.opentimestamps.org, a.pool.eternitywall.com, ots.btc.catallaxy.com

Commands:
    python3 -m venv otsenv && otsenv/bin/pip install opentimestamps-client
    git rev-parse access2026-prereg-manifest-2026-10-21^{commit} > PREREG_MANIFEST_COMMIT.txt
    ots stamp PREREG_MANIFEST.json            # -> PREREG_MANIFEST.json.ots
    ots stamp PREREG_MANIFEST_COMMIT.txt      # -> PREREG_MANIFEST_COMMIT.txt.ots
    ots upgrade <file>.ots                    # run once at stamping time

Status: pending. The first upgrade attempt reported the proofs are not yet Bitcoin-confirmed (expected). Bitcoin attestation normally completes within a few hours (next block confirmations).
Later, re-run:
    ots upgrade PREREG_MANIFEST.json.ots && ots upgrade PREREG_MANIFEST_COMMIT.txt.ots
    ots verify PREREG_MANIFEST.json.ots      # needs the original PREREG_MANIFEST.json next to it
    ots verify PREREG_MANIFEST_COMMIT.txt.ots
Commit the upgraded .ots files afterwards. Full verify needs a local Bitcoin node or a block-explorer-capable setup.
