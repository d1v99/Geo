# 💛 A Surprise For You

A little romantic "pick a box" website to surprise your girlfriend. She opens
a gift box, then sees **three sealed mystery boxes** (massage, lashes, sushi
buffet) and gets to **keep only one** - she picks blind, it reveals with a
flourish, and the other two gently lock with a "saved for another day" note.
Her choice sticks, so she can't refresh and pick again.

**Reset her choice** (so she can pick again, or before you hand her the link):
open the link with `?reset` on the end, e.g. `https://.../geo/?reset`.

Everything lives in a single file: **`index.html`** (plus the photo in
`assets/`). Nothing to install.

## How to see it

Just open `index.html` in any web browser. To share it with her, put it
online for free:

- **GitHub Pages** - *Settings → Pages*, choose this branch, root folder.
  Your link becomes `https://<your-username>.github.io/<repo>/`.
- **Netlify Drop** - drag the folder onto <https://app.netlify.com/drop>.

> Tip: phones cache websites hard. After an update, open the link in a
> private/incognito tab (or add `?v=2` to the end of the URL) to be sure
> you're seeing the latest version.

## How to add or change gifts

Open **`index.html`** and scroll to the block marked
**"⬇ EDIT YOUR GIFTS HERE ⬇"**. That's the only part you change:

- `CONFIG` - her name, your name, the photo, and the messages (including the
  "pick one" prompt and the celebration line shown after she chooses).
- `GIFTS` - each box is a `{ ... }` block; she keeps exactly one. Add or remove
  blocks to change how many boxes she chooses between.
