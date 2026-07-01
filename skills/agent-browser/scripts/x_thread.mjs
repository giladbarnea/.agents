#!/usr/bin/env node
/**
 * x_thread.mjs — fetch the FULL reply tree of an X/Twitter post.
 *
 * Uses x.com's internal GraphQL `TweetDetail` endpoint (what the website itself
 * calls to render a tweet page) and paginates every "show more replies" cursor.
 * This returns far more than search-index endpoints — hundreds of replies vs.
 * the ~40 a `conversation_id:` search surfaces. See references/x-twitter.md.
 *
 * Auth: needs a logged-in account's cookies (auth_token + ct0). Either:
 *   AUTH_TOKEN=... CT0=... node x_thread.mjs <tweetId|url>
 * or pull them from a running debug Chrome over CDP (--from-chrome, default port
 * 9222) if you're logged into x.com in that profile.
 *
 * Output: JSON array of {username, name, text, likes, created, id} on stdout.
 *
 * Fragility (the price of the internal endpoint): the query id and `FEATURES`
 * below are pinned. If X rotates them you'll get HTTP 400/404 — refresh both
 * from a live browser request to graphql/.../TweetDetail. This is expected of an
 * unofficial endpoint, not a bug.
 */
import { request } from 'node:https';

const QUERY_ID = '_NvJCnIjOW__EP5-RF197A'; // TweetDetail; rotates — see header
const BEARER =
  'AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA';
const FEATURES = {"rweb_video_screen_enabled":true,"profile_label_improvements_pcf_label_in_post_enabled":true,"responsive_web_profile_redirect_enabled":true,"rweb_tipjar_consumption_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_exclude_directive_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"premium_content_api_read_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"responsive_web_grok_analyze_button_fetch_trends_enabled":false,"responsive_web_grok_analyze_post_followups_enabled":false,"responsive_web_grok_annotations_enabled":false,"responsive_web_jetfuel_frame":true,"post_ctas_fetch_enabled":true,"responsive_web_grok_share_attachment_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"responsive_web_grok_show_grok_translated_post":false,"responsive_web_grok_analysis_button_from_backend":true,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_grok_image_annotation_enabled":true,"responsive_web_grok_imagine_annotation_enabled":true,"responsive_web_grok_community_note_auto_translation_is_enabled":false,"responsive_web_enhance_cards_enabled":false,"responsive_web_twitter_article_plain_text_enabled":true,"responsive_web_twitter_article_seed_tweet_detail_enabled":true,"responsive_web_twitter_article_seed_tweet_summary_enabled":true};

const args = process.argv.slice(2);
const target = args.find((a) => !a.startsWith('-'));
if (!target) {
  console.error('Usage: node x_thread.mjs <tweetId|url> [--from-chrome[=PORT]]');
  process.exit(1);
}
const tweetId = (target.match(/(\d{5,})/) || [])[1];
if (!tweetId) { console.error(`No tweet id in: ${target}`); process.exit(1); }

const fromChrome = args.find((a) => a.startsWith('--from-chrome'));

async function cookiesFromChrome(port) {
  // CDP Storage.getCookies over the browser-level socket — decrypted, no disk read.
  const { default: WebSocket } = await import('ws').catch(() => {
    console.error('--from-chrome needs the `ws` package: run via `npx -y ws ...` or set AUTH_TOKEN/CT0 directly.');
    process.exit(1);
  });
  const ver = await fetch(`http://localhost:${port}/json/version`).then((r) => r.json());
  const ws = new WebSocket(ver.webSocketDebuggerUrl, { origin: '' });
  await new Promise((res) => ws.on('open', res));
  const cookies = await new Promise((res) => {
    ws.on('message', (m) => {
      const msg = JSON.parse(m);
      if (msg.id === 1) res(msg.result.cookies);
    });
    ws.send(JSON.stringify({ id: 1, method: 'Storage.getCookies' }));
  });
  ws.close();
  const x = Object.fromEntries(
    cookies.filter((c) => c.domain.endsWith('x.com')).map((c) => [c.name, c.value]));
  return { authToken: x.auth_token, ct0: x.ct0 };
}

let authToken = process.env.AUTH_TOKEN;
let ct0 = process.env.CT0;
if ((!authToken || !ct0) && fromChrome) {
  const port = fromChrome.includes('=') ? fromChrome.split('=')[1] : '9222';
  ({ authToken, ct0 } = await cookiesFromChrome(port));
}
if (!authToken || !ct0) {
  console.error('No credentials. Set AUTH_TOKEN and CT0, or pass --from-chrome with x.com logged in.');
  process.exit(1);
}

function get(path) {
  return new Promise((resolve, reject) => {
    const req = request(
      { hostname: 'x.com', path, method: 'GET', headers: {
        accept: '*/*', authorization: `Bearer ${BEARER}`,
        'x-csrf-token': ct0, 'x-twitter-auth-type': 'OAuth2Session',
        'x-twitter-active-user': 'yes', 'x-twitter-client-language': 'en',
        cookie: `auth_token=${authToken}; ct0=${ct0}`,
        'user-agent': 'Mozilla/5.0', origin: 'https://x.com', referer: 'https://x.com/',
      } },
      (res) => { let b = ''; res.on('data', (d) => (b += d));
        res.on('end', () => res.statusCode === 200 ? resolve(JSON.parse(b))
          : reject(new Error(`HTTP ${res.statusCode}: ${b.slice(0, 300)}`))); });
    req.on('error', reject); req.end();
  });
}

function pageUrl(cursor) {
  const variables = {
    focalTweetId: tweetId, referrer: 'tweet', with_rux_injections: false,
    includePromotedContent: false, withCommunity: true,
    withQuickPromoteEligibilityTweetFields: false, withBirdwatchNotes: false,
    withVoice: true, withV2Timeline: true, ...(cursor ? { cursor } : {}),
  };
  const p = new URLSearchParams({
    variables: JSON.stringify(variables), features: JSON.stringify(FEATURES) });
  return `/i/api/graphql/${QUERY_ID}/TweetDetail?${p}`;
}

const all = [];
const seen = new Set();
let cursor, pages = 0;
while (pages < 40) {
  const data = await get(pageUrl(cursor));
  const entries = data?.data?.threaded_conversation_with_injections_v2?.instructions
    ?.flatMap((i) => i.entries || []) || [];
  let next = null;
  const collect = (r) => {
    const t = r?.tweet || r; const lg = t?.legacy;
    const u = t?.core?.user_results?.result?.core;
    if (lg && !seen.has(lg.id_str)) {
      seen.add(lg.id_str);
      all.push({ id: lg.id_str, username: u?.screen_name, name: u?.name,
        text: lg.full_text, likes: lg.favorite_count, created: lg.created_at });
    }
  };
  for (const e of entries) {
    const ic = e.content?.itemContent;
    if (ic?.tweet_results?.result) collect(ic.tweet_results.result);
    if (e.content?.cursorType === 'Bottom') next = e.content.value;
    for (const it of e.content?.items || []) {
      const r = it.item?.itemContent?.tweet_results?.result;
      if (r) collect(r);
      if (it.item?.itemContent?.cursorType === 'Bottom') next = it.item.itemContent.value;
    }
  }
  pages++;
  if (!next || next === cursor) break;
  cursor = next;
}
console.error(`pages=${pages} replies=${all.length}`);
process.stdout.write(JSON.stringify(all));
