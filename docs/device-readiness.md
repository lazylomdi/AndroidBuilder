# Device readiness assessment

Run an offline report without a connected phone:

```bash
python3 romforge.py ut-check \
  --manufacturer Sony --model "Xperia R1" --ram-gb 2 \
  --json-out reports/xperia-r1.json \
  --markdown-out reports/xperia-r1.md
```

Optional inputs include `--codename`, `--android-version`, `--kernel-version`, and `--bootloader-unlock yes|no|unknown`. Omitted values remain unknown. Reports are preliminary evidence inventories, not compatibility certifications. A candidate source repository is not proof of a successful build; a successful build is not proof of bootability or working radio, graphics, Wi-Fi, camera, audio, sensors, or power management.

Statuses are `VERIFIED`, `CANDIDATE`, `UNKNOWN`, `BLOCKED`, and `NOT_APPLICABLE`. This initial checker uses `CANDIDATE` for user-provided data and `UNKNOWN` for facts without independent evidence. It does not yet mark device-specific facts `VERIFIED`.
