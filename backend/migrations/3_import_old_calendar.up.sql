-- The events of the old calendar, houseofsoftbeasts.se/calendar (Wix Events),
-- as they were on 2026-11-16: 20 August to 30 December 2026. Every one was at
-- the house, so none has a location of its own. They were made by no member
-- of this calendar, so an event's creator may now be unknown.
ALTER TABLE events ALTER COLUMN created_by DROP NOT NULL;

INSERT INTO events (title, description, starts_at, ends_at, capacity) VALUES
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-08-20T08:00:00Z', '2026-08-20T16:00:00Z', NULL),
    ('Make It Weird', 'Come spend an evening making weird little things for the House of Soft Beasts. We’ll have materials, tools, snacks, drinks, and a bunch of half-formed ideas waiting to become something.', '2026-08-20T16:00:00Z', '2026-08-20T18:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-08-21T08:00:00Z', '2026-08-21T16:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-08-27T08:00:00Z', '2026-08-27T16:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-08-28T08:00:00Z', '2026-08-28T16:00:00Z', NULL),
    ('Murder Your Darlings', 'A low-stakes reading night for writers to share the work that’s still messy, unfinished, questionable, or otherwise not quite ready for the world. Bring a draft, fragment, bad idea, abandoned darling, or something you’re still trying to figure out and read it aloud.', '2026-09-07T16:00:00Z', '2026-09-07T18:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-09-10T08:00:00Z', '2026-09-10T16:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-09-11T08:00:00Z', '2026-09-11T16:00:00Z', NULL),
    ('Night Owl Nerd Out', 'A cozy night for the nerds. Come play board games, card games, tabletop games, or whatever else we collectively decide deserves our attention. Bring your favorite game, join something already in progress, or just come hang out and get mildly competitive.', '2026-09-14T16:00:00Z', '2026-09-14T18:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-09-17T08:00:00Z', '2026-09-17T16:00:00Z', NULL),
    ('Warhammer & Chill', 'Paint tiny dudes. Drink something. Hang out.', '2026-09-17T16:30:00Z', '2026-09-17T19:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-09-18T08:00:00Z', '2026-09-18T16:00:00Z', NULL),
    ('The House Dinner: September', 'Come eat, drink, and spend an evening around the table.', '2026-09-18T16:00:00Z', '2026-09-18T19:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-09-24T08:00:00Z', '2026-09-24T16:00:00Z', NULL),
    ('Polegasm', 'A sweaty little celebration of pole, performance, play, and self-expression.', '2026-09-24T16:00:00Z', '2026-09-24T19:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-09-25T08:00:00Z', '2026-09-25T16:00:00Z', NULL),
    ('Second-Rate Cinema', 'A recurring night for movies that probably didn''t deserve a second viewing, but we''re giving them one anyway.', '2026-09-26T17:00:00Z', '2026-09-26T19:30:00Z', NULL),
    ('Procrastination Club', 'An evening dedicated to all the things you keep meaning to do but somehow never quite get around to.', '2026-09-28T16:00:00Z', '2026-09-28T19:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-10-01T08:00:00Z', '2026-10-01T16:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-10-02T08:00:00Z', '2026-10-02T16:00:00Z', NULL),
    ('Ecstatic Dance', 'An evening of movement, music, and getting out of your head.

Ecstatic Dance is a freeform dance practice with no choreography and no right or wrong way to move. Come as you are, listen to the music, and let your body do whatever it wants to do.

No dance experience necessary.', '2026-10-02T16:00:00Z', '2026-10-02T18:00:00Z', NULL),
    ('Candlelit Croquis: Night of the Muses', 'An intimate evening of drawing, candlelight, and the human form led by Lindsay Balfour (@essente)', '2026-10-05T16:00:00Z', '2026-10-05T19:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-10-08T08:00:00Z', '2026-10-08T16:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-10-09T08:00:00Z', '2026-10-09T16:00:00Z', NULL),
    ('Bounce & Bubbles', 'An evening of house, bounce, and dance music with DJs keeping things moving.

Come dance, have a drink, and hang out. No agenda beyond good music and a reason to stay on the dance floor.', '2026-10-09T16:00:00Z', '2026-10-09T22:30:00Z', NULL),
    ('Costume Exchange', 'One person''s forgotten costume is another person''s treasure.

Bring along costumes, accessories, wigs, props, or other bits of dress-up you no longer need and swap them.', '2026-10-12T16:00:00Z', '2026-10-12T18:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-10-15T08:00:00Z', '2026-10-15T16:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-10-16T08:00:00Z', '2026-10-16T16:00:00Z', NULL),
    ('Drag After Dark', 'Music, drag, cocktails, and a little bit of glamour.', '2026-10-16T16:30:00Z', '2026-10-16T20:00:00Z', NULL),
    ('Build a Body', 'What if you could make a mannequin shaped to your own body?', '2026-10-19T16:00:00Z', '2026-10-19T19:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-10-22T08:00:00Z', '2026-10-22T16:00:00Z', NULL),
    ('Dances of Moldova', 'Learn some traditional dances from Moldova in a relaxed, social evening of movement and music led by Christian Ovidiu Cemirtan of the Moldovan Folk Dance School!

No dance experience or partner required: just bring yourself, comfortable clothes, and a willingness to give it a try.', '2026-10-22T16:00:00Z', '2026-10-22T18:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-10-23T08:00:00Z', '2026-10-23T16:00:00Z', NULL),
    ('Stitch & Bitch', 'Bring your project. Bring your complaints.', '2026-10-25T17:00:00Z', '2026-10-25T20:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-10-29T09:00:00Z', '2026-10-29T17:00:00Z', NULL),
    ('Make It Weird', 'Bring whatever you’re currently making: knitting, crochet, embroidery, drawing, painting, collage, a half-finished project you’ve been ignoring for six months, whatever. Or come empty-handed and just hang out.', '2026-10-29T17:00:00Z', '2026-10-29T21:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-10-30T10:00:00Z', '2026-10-30T18:00:00Z', NULL),
    ('The Last Harvest', 'A feast for the turning of the year.

On Halloween, we gather for an intimate Samhain supper in the house. A candlelit evening of seasonal food, wine, music, ritual, and magic.', '2026-10-31T17:30:00Z', '2026-10-31T22:00:00Z', NULL),
    ('Night Owl Nerd-out', 'Games for the deeply invested and casually obsessed.

This time, we’re getting nostalgic with the classics: cards, bridge, gin rummy, backgammon, chess, and whatever else you remember your grandparents absolutely destroying you at.', '2026-11-02T17:00:00Z', '2026-11-02T20:30:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-11-05T09:00:00Z', '2026-11-05T17:00:00Z', NULL),
    ('Stick It & Kick It', 'Stand-up meets pole. What could go wrong?', '2026-11-05T17:00:00Z', '2026-11-05T21:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-11-06T09:00:00Z', '2026-11-06T17:00:00Z', NULL),
    ('In Vino Veritas', 'Let''s talk about wine without making it complicated.', '2026-11-06T17:00:00Z', '2026-11-06T20:00:00Z', NULL),
    ('Mini Beasts', '🧸 MINI BEASTS is coming to the house! A cozy afternoon of play, crafts, music, fika, and hanging out for our littlest beasts and their grown-ups. 💛', '2026-11-07T11:00:00Z', '2026-11-07T14:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-11-11T09:00:00Z', '2026-11-11T17:00:00Z', NULL),
    ('Melt: Deep Stretch and Hammock Meditation', '', '2026-11-11T18:00:00Z', '2026-11-11T20:00:00Z', 6),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-11-12T09:00:00Z', '2026-11-12T17:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-11-13T09:00:00Z', '2026-11-13T17:00:00Z', NULL),
    ('Stitch Craft', 'Advanced sewing with Madame Dragonfly', '2026-11-16T17:00:00Z', '2026-11-16T20:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-11-18T09:00:00Z', '2026-11-18T17:00:00Z', NULL),
    ('Come As You Are: Open House Fika', '', '2026-11-18T15:00:00Z', '2026-11-18T17:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-11-19T09:00:00Z', '2026-11-19T17:00:00Z', NULL),
    ('Candlelight Cabaret', '', '2026-11-19T17:00:00Z', '2026-11-19T21:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-11-20T09:00:00Z', '2026-11-20T17:00:00Z', NULL),
    ('Come As You Are: Open House Fika', '', '2026-11-22T10:00:00Z', '2026-11-22T12:00:00Z', NULL),
    ('Freedom in Movement and Dance Workshop', '', '2026-11-22T13:00:00Z', '2026-11-22T16:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-11-25T09:00:00Z', '2026-11-25T17:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-11-26T09:00:00Z', '2026-11-26T17:00:00Z', NULL),
    ('The House Dinner: Thanksgiving', 'Come eat, drink, and spend an evening around the table.', '2026-11-26T17:00:00Z', '2026-11-26T21:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-11-27T09:00:00Z', '2026-11-27T17:00:00Z', NULL),
    ('Read and Resonance', 'An evening of books, ambient sounds, and quiet company.', '2026-11-29T17:00:00Z', '2026-11-29T21:00:00Z', NULL),
    ('Meet Your Inner Critic', '', '2026-11-30T17:00:00Z', '2026-11-30T19:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-12-02T09:00:00Z', '2026-12-02T17:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-12-03T09:00:00Z', '2026-12-03T17:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-12-04T09:00:00Z', '2026-12-04T17:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-12-09T09:00:00Z', '2026-12-09T17:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-12-10T09:00:00Z', '2026-12-10T17:00:00Z', NULL),
    ('Party in the Dressing Room', 'Because getting ready is the best part.', '2026-12-10T17:00:00Z', '2026-12-10T21:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-12-11T09:00:00Z', '2026-12-11T17:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-12-16T09:00:00Z', '2026-12-16T17:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-12-17T09:00:00Z', '2026-12-17T17:00:00Z', NULL),
    ('Sword, Breath, and Presence', '', '2026-12-17T17:30:00Z', '2026-12-17T19:30:00Z', 10),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-12-18T09:00:00Z', '2026-12-18T17:00:00Z', NULL),
    ('The House Dinner: Christmas', 'Come eat, drink, and spend an evening around the table.', '2026-12-19T17:00:00Z', '2026-12-19T21:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-12-23T09:00:00Z', '2026-12-23T17:00:00Z', NULL),
    ('House Hours', 'Come work from the house for the day. Bring your laptop, settle in, make some tea, chat, focus, take a break... whatever your workday needs.

Tea, coffee, and snacks will be available throughout the day, and we’ll have a shared lunch around midday.', '2026-12-30T09:00:00Z', '2026-12-30T17:00:00Z', NULL);
