# 💛 A Surprise For You

A little romantic website to surprise your girlfriend with gifts — like a
personal collection of gift cards (a massage, lashes, nails, date night…).
She opens a gift box, flips each card to reveal the surprise, and gets a
voucher code to "redeem" with you.

Everything lives in a single file: **`index.html`** (plus the photo in
`assets/`). Nothing to install.

## How to see it

Just open `index.html` in any web browser. To share it with her, put it
online for free:

- **GitHub Pages** — *Settings → Pages*, choose this branch, root folder.
  Your link becomes `https://<your-username>.github.io/<repo>/`.
- **Netlify Drop** — drag the folder onto <https://app.netlify.com/drop>.

> Tip: phones cache websites hard. After an update, open the link in a
> private/incognito tab (or add `?v=2` to the end of the URL) to be sure
> you're seeing the latest version.

## How to add or change gifts

Open **`index.html`** and scroll to the block marked
**"⬇ EDIT YOUR GIFTS HERE ⬇"**. That's the only part you change:

- `CONFIG` — her name, your name, the photo, and the messages.
- `GIFTS` — each gift is a `{ ... }` block; copy one, edit the words, save.

Each gift's `status`:

| status        | what she sees                                   |
|---------------|-------------------------------------------------|
| `"available"` | ready to flip + redeem (shows a gift code)      |
| `"soon"`      | stays a mystery, marked "Coming soon"           |
| `"redeemed"`  | shown with a "REDEEMED" stamp once it's used    |
