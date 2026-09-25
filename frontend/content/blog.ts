export type Block = { type: "p"; text: string } | { type: "h2"; text: string } | { type: "ul"; items: string[] };

export interface BlogPost {
  slug: string;
  title: string;
  description: string;
  date: string; // ISO
  readingMinutes: number;
  author: string;
  body: Block[];
}

export const posts: BlogPost[] = [
  {
    slug: "teach-dont-sell-small-business-social-media",
    title: "Teach, don't sell: why helpful posts beat promotions for small businesses",
    description:
      "Promotional posts feel productive, but helpful posts are the ones people save and share. How to find the right mix for your business, and how to check it with your own numbers.",
    date: "2026-09-08",
    readingMinutes: 5,
    author: "ContentFactory team",
    body: [
      { type: "p", text: "Most small business feeds drift towards the same thing: offers, new arrivals, opening hours. They're easy to write and they feel like marketing. But a feed of announcements gives people little reason to stop scrolling, and almost no reason to save a post or send it to a friend." },
      { type: "h2", text: "What a helpful post looks like" },
      { type: "p", text: "A helpful post answers a question your customers already have. A café can explain why its cold brew tastes smoother than iced coffee. A salon can show how to make a blow-dry last three days. A bike shop can list the five checks to do before a long ride." },
      { type: "ul", items: ["It's useful even to someone who never buys from you", "It shows expertise instead of claiming it", "It's the kind of thing people save for later or send to a friend"] },
      { type: "h2", text: "You still need to sell" },
      { type: "p", text: "Helpful content earns attention; promotional content converts it. The question isn't whether to promote, but how often. Many businesses start with roughly two helpful or behind-the-scenes posts for every promotional one, then adjust." },
      { type: "h2", text: "Check it with your own numbers" },
      { type: "p", text: "General advice is only a starting point. Your audience may behave differently. Tag each post by type, wait until you have a reasonable number of posts in each group, then compare saves, shares and reach per post over the same period." },
      { type: "p", text: "Be careful with small samples. Three posts are not a trend. ContentFactory's Marketing Intelligence won't state a conclusion until each group has enough posts, and it always shows the sample size and period so you can judge for yourself." },
    ],
  },
  {
    slug: "how-often-should-a-small-business-post",
    title: "How often should a small business post on social media?",
    description:
      "There's no magic number. A practical way to choose a posting rhythm you can keep up, and how to adjust it based on results rather than guesswork.",
    date: "2026-08-25",
    readingMinutes: 4,
    author: "ContentFactory team",
    body: [
      { type: "p", text: "Ask ten marketers how often to post and you'll hear ten numbers. The honest answer is that consistency matters more than volume. A rhythm you can sustain for six months beats a burst of daily posts that stops after three weeks." },
      { type: "h2", text: "Start with what you can keep up" },
      { type: "ul", items: ["Three posts a week on your main platform is a realistic start for most small teams", "Add short video once a week if your platform rewards it", "Use stories for day-to-day moments that don't need polish"] },
      { type: "h2", text: "Pick your main platform first" },
      { type: "p", text: "Spreading thin across five platforms usually means doing all of them badly. Choose the platform where your customers already spend time, get a steady rhythm there, then expand." },
      { type: "h2", text: "Let results adjust the plan" },
      { type: "p", text: "After a month, look at reach and engagement per post, not just totals. If posting more often lowers the quality of each post, the extra volume may not be helping. If a particular day or time keeps performing better, move more posts there." },
      { type: "p", text: "ContentFactory drafts posts from your goals and brand, and learns which topics, formats and times work from your own results. You approve every post unless you choose to turn approval off." },
    ],
  },
  {
    slug: "use-your-own-photos-in-marketing",
    title: "Your own photos are your best marketing asset. Here's how to use them",
    description:
      "Real photos of your products, space and people build trust in a way stock images can't. A practical guide to capturing, organising and reusing them.",
    date: "2026-08-11",
    readingMinutes: 5,
    author: "ContentFactory team",
    body: [
      { type: "p", text: "Customers want to see what they'll actually get: the real dish, the real room, the real person who'll cut their hair. Your own photos do that. They don't need to be perfect, but they do need to be clear, well lit and organised so you can find them when you need them." },
      { type: "h2", text: "Capture in batches" },
      { type: "ul", items: ["Set aside 30 minutes a week with good daylight", "Shoot each product from a few angles, plus one in use", "Take short vertical clips; they become Reels and stories later", "Photograph your space when it's busy and when it's calm"] },
      { type: "h2", text: "Organise so you can reuse" },
      { type: "p", text: "A photo you can't find is a photo you'll never use. Name files clearly, group them into folders by product or theme, and add a few tags: what's in the picture, the season, the mood." },
      { type: "h2", text: "Let generated images fill gaps, not replace you" },
      { type: "p", text: "AI-generated images are useful for seasonal backgrounds, carousel covers or ideas you haven't photographed yet. But they work best alongside your real photos, not instead of them." },
      { type: "p", text: "In ContentFactory, you choose how strongly the agent should prefer your own media: always, when relevant, or never. Tags and descriptions help it pick the right photo for each post, and anything it generates is saved to your library so it's never paid for twice." },
    ],
  },
];

export function postBySlug(slug: string): BlogPost | undefined {
  return posts.find((p) => p.slug === slug);
}

export function formatDate(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
}
