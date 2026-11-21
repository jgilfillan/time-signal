# Pi set-up: making give-away transmitters

This folder turns a Raspberry Pi Zero W / Zero 2 W with the time-signal pHAT
into a plug-and-play gadget. The person you give it to only has to:

1. plug it in, and
2. pick their home Wi-Fi from their phone.

It then waits for internet time and starts transmitting JJY60 (or whichever
station you choose) automatically. A status page shows what it's sending.

You do the set-up once on a **master** Pi, turn that card into an image, and
write the image to every card you give away.

## What the recipient gets

- **First power-up:** the Pi can't find a known Wi-Fi network, so it opens its
  own hotspot named after the device, e.g. `jjy-1a2b`. Joining it from a phone
  pops up a page to choose their Wi-Fi and enter the password (this is
  [Comitup](https://davesteele.github.io/comitup/)).
- **After that:** it joins their Wi-Fi at every boot, syncs the clock from the
  internet, then starts transmitting. Until the clock is synced it will not
  transmit, so it can never set a watch to the wrong time.
- **Status page:** `http://jjy-1a2b.local:8080` (or the IP shown on the page)
  shows the station, the time being sent, whether the clock is synced, and the
  live log. They can also change station there.
- **Pulling the plug is safe:** with the read-only root switched on, every
  boot starts from the clean image. Only the Wi-Fi settings and the app's
  settings are written, to a small separate partition.
- **If they move house:** when the saved Wi-Fi isn't found, the hotspot comes
  back so they can pick the new network.

## One image for both Pi models

Use **Raspberry Pi OS Lite (32-bit)**. It runs on both the Pi Zero W and the
Pi Zero 2 W, so one image covers both. (The 64-bit build won't boot on the
original Zero W.)

## Step 1 — set up the master Pi

1. Flash Raspberry Pi OS Lite (32-bit) with Raspberry Pi Imager. In its
   settings, set a username/password, your Wi-Fi, and enable SSH so you can
   log in for set-up.
2. Boot it, log in, then:

   ```bash
   sudo apt update && sudo apt install -y git
   git clone https://github.com/jgilfillan/time-signal.git
   cd time-signal
   sudo ./pi-setup/setup-appliance.sh --service JJY60 --country AU --keep-ssh
   sudo reboot
   ```

   Options: `--service` (default JJY60), `--prefix` for the device names
   (default `jjy` → `jjy-1a2b`), `--country` Wi-Fi country (default AU),
   `--keep-ssh` to leave SSH on while you test, `--enable-overlay` to switch
   on the read-only root (do that last).

3. **Test it.** After the reboot it still joins your Wi-Fi (the data
   partition doesn't exist yet, so it uses the settings you flashed). Open
   `http://<hostname>.local:8080`, check the clock shows *Synced* and a watch
   picks up the signal.
4. When you're happy, lock it down and switch SSH off:

   ```bash
   sudo ./pi-setup/setup-appliance.sh --service JJY60 --country AU --enable-overlay
   sudo poweroff
   ```

   (Running it again is safe; it just re-applies the settings.)

## Step 2 — make the give-away image (on a Linux PC)

1. Put the master card in a Linux PC (WSL2 on Windows also works with a USB
   card reader passed through) and copy it to a file:

   ```bash
   lsblk                                   # find the card, e.g. /dev/sdb
   sudo dd if=/dev/sdX of=master.img bs=4M status=progress conv=fsync
   ```

2. Build the image:

   ```bash
   sudo ./pi-setup/build-image.sh master.img time-signal-appliance.img
   ```

   This works on a copy and never changes `master.img`. It shrinks the root
   filesystem, adds the 64 MB data partition (label `tsdata`), removes your
   saved Wi-Fi, machine-id, shell history, logs and test config, and trims
   the image so it fits any card the same size or bigger.

## Step 3 — write the cards

Write `time-signal-appliance.img` to each card with Raspberry Pi Imager
(**Choose OS → Use custom**, and don't apply any OS customisation) or `dd`.
Each Pi gives itself its own name from its serial number on first boot.

Write the device name on a label on each box with the address, e.g.
`jjy-1a2b` and `http://jjy-1a2b.local:8080`. Power one up once to read
its name from the hotspot list. Hand over [the quick-start guide](../docs/QUICKSTART.md) with it.

## Notes and limits

- **`.local` names** work on iPhone, Mac, Windows and Linux, but not on every
  Android phone. The status page also shows the IP address, and most routers
  list the device by name.
- **Updating units already given away:** with the read-only root on, nothing
  changes on the card. Re-flash with a new image to update.
- **Factory reset of Wi-Fi:** re-flash the card, or (if you turn on Comitup's
  `enable_nuke` option) short GPIO pins 39 and 40 for three seconds.
- **The image's root filesystem is not expanded** to fill bigger cards. That's
  intentional: nothing is written to it.
- **SSH:** off by default. If you keep it on, every card shares the same
  password and SSH host keys; change the password first.
- **Legal:** check your local rules for low-power transmitters (in Australia,
  the ACMA LIPD class licence).
