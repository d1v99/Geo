# 💛 A Surprise For You

A little romantic website to surprise your girlfriend with gifts — like a
personal collection of gift cards (a massage, lashes, nails, date night…).
She opens a gift box, flips each card to reveal the surprise, and gets a
voucher code to "redeem" with you.

## How to use it

**To see it:** just open `index.html` in any web browser. That's it — no
installation, no build step.

**To send it to her:** put it online for free (pick one):

- **Netlify Drop** — go to <https://app.netlify.com/drop> and drag the whole
  folder in. You get a link instantly.
- **GitHub Pages** — in this repo go to *Settings → Pages*, set the branch,
  and your site goes live at a github.io link.
- **Vercel** — import the repo at <https://vercel.com/new>.

Then text her the link. 💌

## How to add or change gifts

Open **`gifts.js`** — it's the only file you need to touch. Everything is
explained with comments at the top. In short:

- Edit `CONFIG` to set her name, your name, the messages, and the photo
  (`photo: "assets/us.jpeg"` — swap in any image, or set it to `""` to hide it).
- Each gift is a `{ ... }` block in the `GIFTS` list. Copy one, paste it,
  change the words, save.

Each gift's `status` controls how it shows:

| status        | what she sees                                  |
|---------------|------------------------------------------------|
| `"available"` | ready to flip + redeem (shows a gift code)     |
| `"soon"`      | stays a mystery, marked "Coming soon"          |
| `"redeemed"`  | shown with a "REDEEMED" stamp once she's used it|

That's the whole idea: keep adding new gifts over time and the page becomes
an ongoing little stream of surprises.

## Files

- `index.html` — the page
- `styles.css` — the looks
- `script.js` — the behaviour (you can ignore this)
- `gifts.js` — **your gifts & messages (edit this)**
