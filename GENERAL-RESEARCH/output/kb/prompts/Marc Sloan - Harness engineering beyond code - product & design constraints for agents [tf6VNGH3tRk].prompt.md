<!-- transcript_hash: sha256-8977fb806fc88cbe -->
# Summarise this video transcript

You are given the FULL transcript of a YouTube video. The transcript comes from YouTube's own
captions, so it may contain caption mistakes, filler words ("you know", repeated words),
`[music]` tags and `>>` speaker-change markers.

**Video:** Marc Sloan - Harness engineering beyond code - product & design constraints for agents - AI Native D
**Source:** https://www.youtube.com/watch?v=tf6VNGH3tRk

## Write, in Markdown, in this order
1. **TL;DR** — at most 3 sentences: the single most useful takeaway.
2. **Key points** — bullets; each one must be supported by the transcript.
3. **Names & terms** — tools, products, people, numbers mentioned. If a caption error is
   obvious and you are certain (e.g. "cloud code" -> "Claude Code"), correct it and list the
   correction here.
4. **Unclear parts** — anything ambiguous or garbled in the transcript.

## Rules
- Use ONLY the transcript below. Do not add facts it does not contain.
- If something is unclear, say so instead of guessing.
- Keep it short and skimmable.

Save your answer as: `kb/highlights/Marc Sloan - Harness engineering beyond code - product & design constraints for agents [tf6VNGH3tRk].md`

--- TRANSCRIPT START ---
Hello everyone, nice to see you. Really
exciting to be here helping to kick off
day two of Devcon. Um and I'm impressed
by the number of people in the room
today. You have made it through the
weather, the tube strikes,
uh and you're here. I know I had my own
battle to get here this morning as well.
Um I'm Mark Sloan. I'm a member of the
product team here at Seso. And I'm here
today at a developer-focused conference
to talk about non-developers.
Now,
I don't know if there are any other
non-developers in the room here today.
Um I'm thinking probably Yeah, there we
go. Product managers, designers,
executives, you know, the people who
traditionally wouldn't touch code,
although I think we're all talk we're
all turning into developers these days,
right? Um
this talk is about the work that they
create, but also it is for everyone,
rest assured. Um because as we talk
increasingly about the context that we
give agents, coding agents,
um
a lot of that the origination of that
context comes from non-developers, comes
from product and design teams. And so
what I'm going to talk about today is
the creation of that context, the
challenges we face in exposing that to
our coding agents and their harnesses,
and what solutions to those challenges
might look like.
Now, over the last 24 hours, the
conversation at Devcon has been pretty
much about one thing, and that's giving
agents the right context. Um I think
it's been super interesting working in
this area over the last 6 to 12 months,
and we've seen the methodology we used
to do that evolving from spec driven
development, where we write up front all
the context that the agent's going to
need in order to get the task done, to
context engineering, which is kind of
where we are just now, um and how that's
evolving into harness engineering.
And
the tools are maturing really fast in
this area,
but a lot of it has been focused on
context that originates and lives within
the code base.
And the natural form that that context
has been taking
recently has been in the form of skills.
Now, I don't think I need to convince
anybody here of the
the value of skills and how powerful
they are. Um there was a great quote in
one of the talks yesterday about how the
simplest solution is often the right
one. And the fact that the the markdown
file is so flexible and adaptable makes
it the natural place to be able to put
code-based context. Um I think another
powerful aspect of it is the fact that
that context can live alongside the code
that it's describing.
That it lives within the repo, that it's
managed, it's versioned, and can be
subject to evaluations and tests, and
all that good stuff that comes with the
harness.
And we're still figuring out how to
manage that kind of context, right? All
the stuff we've been talking about with
harness engineering, the the features
that you see in the Tesla product are
all about figuring out how we turn
skills and context into code.
So, to kick us off
and to kick off this conversation about
product and design context, I'm going to
walk through
a typical example, the kind of thing I'm
sure everybody in this room is familiar
to everybody in this room.
We're going to describe a scenario here
where we've got a company that has a web
app product, and a customer has asked
the product manager to put an export
button on the dashboard in that product.
Now,
the export feature was something that
was hidden behind the settings menu, and
it was a couple of layers deep, so it
was very difficult to find. Customer
wasn't aware that it existed, and
requested this to be in a more prominent
position.
On the surface, this seems like the
perfect kind of
job to give to an agent.
Write a linear ticket that describes it,
put a Figma design in there that shows
where the button should go, what it
should look like, all that good stuff.
Fire it off to your agent, have it
produce a PR, job done. Customer's
happy. The feature got delivered, the
customer tried it out and said it's
great. So, cool.
This is the the world we live in right
now. We can just
uh send these things off to agents. And
of course, the agent wasn't building
this blind.
It had access to a bunch of skills that
had been developed in advance to
instruct the agent on how it should be
uh thinking about the architecture of
the code, about the front-end components
that live within that,
the testing and CR requirements, and how
to make use of the API to get the data.
And of course,
this is a uh cutting-edge,
state-of-the-art company, so they're
using Tessel to manage all of this
stuff.
So, problem solved.
Why do we need to be thinking about
product and design context? Well, in
this scenario,
the agent got one thing wrong.
It actually ended up using a generic
React button component that lived within
the code base, and not the more specific
export button component that was the
right choice here.
And this might seem like a trivial
error,
but encoded within that export button
components are the accessibility
requirements that this organization
adheres to, interaction patterns that
make sense for this kind of async the
the async operation of this kind of
button.
And this was all missed by the agent in
creating this.
And what's challenging here is that as
far as the harness was concerned,
everything went smoothly. The agent got
a ticket handed off to it, did the job,
created a PR that passed, and the
feature went out to the customer. The
evaluations that were set up on the
skills and the other aspects of the
harness all seem to be working well,
but the product and design context was
missing from the agent in this
particular situation.
And this can have real-world
consequences because while the customer
was happy out of the bat in this
situation, it might be that down the
line the app then ends up failing an
accessibility audit that delays a
critical deal, and that kind of stuff.
So, we might ask ourselves, well, how
should the agent have learned about
that? How can it find the right context
to do it? Well, the context was in the
design system in Figma this whole time.
It turns out that
the design system team had thought this
stuff through and already thought about
how this button should be created, how
it should be designed, and how the
interaction should work with it.
In fact, the Figma design that was in
that original linear ticket did
correctly use the export button design
component, but the agent just didn't
pick this up. It used the Figma design
as a visual treatment, and then from
that inferred that it should be using a
generic button that it customized.
So,
as we think about building agent
harnesses as we've been doing for the
last 24 hours in this conference,
we might ask ourselves, where does
product and design context fit into
this?
Now, the way I think about agent
harnesses is that it's a layer that
wraps the code base itself, and that
layer contains skills, evaluations,
hooks, policies, all this other stuff
that we're working on
uh at the moment, and we're using tools
like Tessel to manage.
The product and design context I see
existing in this layer surrounding the
harness, at least right now.
And it's not just that it's a layer
outside of the harness, but this data
doesn't live in the code base by design.
It lives in the third-party tools that
product managers and designers and so on
are using day-to-day.
Every day context is getting created in
these third-party tools,
and the code base is blind to it and
therefore the agent and the agent
harness as well.
And it makes sense that it lives in
those tools because that's the tools
where product managers and designers and
more are spending their time. Designers
are going to continue to work in Figma
because it has a canvas and a great set
of tools for creating designs. PMs will
keep working in Linear and Notion and
more. Customer data is going to continue
to live in CRMs.
And for as long as that keeps happening,
we're going to have important context
that agents need in order to build the
right things and do the right job living
outside the code base.
And not just the context need agents
need to get the job done, but also the
context we need to understand whether
the job got done correctly.
So, challenge one is the fact that
product and design context is important
to agents, but it lives outside the code
base.
If we go back to our example, let's
imagine the team has picked up on this
and decided to try and bring that
context into the code base in order to
solve this problem.
They've set up Storybook. They've gone
through the design system in Figma and
made sure all of the design components
that are there are well represented in
Storybook with the appropriate
documentation and interaction patterns
and so on.
This means the next time a request like
this comes in,
the agent picks up the right the right
component correctly and gets the job
done.
Perfect. This is all working.
But,
the world keeps evolving and the product
and design context isn't static. You can
imagine in this situation something like
this where a new deal comes in and with
this new deal comes a new set of
accessibility requirements, let's say.
Let's say it's a government agency.
The PM picks this up and produces a
Notion document that outlines what those
requirements are.
The fig- the design team update Figma
and the design components there to make
sure that they are fully compliant. And
while all that's going on, the code base
is falling increasingly out of sync with
what's going on in product and design
land.
And the agent is still producing
features using the outdated design
system.
And so, for as long as we accept that
product and design context is going to
live outside the code base,
then we're going to have this problem of
the two falling out of sync with each
other.
And I've talked about this in one
direction so far
with the product and design context
evolving as the code stays the same, but
the opposite is also true. And
especially as we have more and more
agents
being thrown into the code base and
building new components from scratch and
updating existing components, we're also
going to find ourselves in the situation
where
the app itself has a whole bunch of
components the design team know nothing
about. And so, we need to be able to
move the context in the other direction
for them as well.
Now, in all of this, you might be
thinking, "Isn't this a solved problem?
Surely all the- these tools have MCP
service today. Isn't it just a case of
connecting the agent to the MCP server
and we're done?"
That's true to an extent,
but
the fact that we need to have this live
connection to third-party product and
design context also introduces a set of
new challenges, especially as we now
start to think about the agent harness
as being something that's managed and
controlled, and we want to be improving
all of the time.
We now have a live connection that we
need to maintain and work around the
rate limits that that imposes, cost
constraints, and the third-party
availability.
We also get into a situation where the
evals and things like that that we're
setting up on the skills in the context
in the code base is now reliant on
third-party context that's constantly
changing that doesn't necessarily have a
canonical source of truth. And of course
that's the problem with product and
design context. It is constantly
up-to-date. There's never really a
definition of done there.
Um it can be in an incomplete state by
virtue of its nature.
And so if we're building harnesses that
are reliant on that, we have to be very
careful about how we make that work.
So let's pause for a moment to reflect
on what we've established here.
I'm saying that for agents to work
effectively and for the harnesses that
use them to work effectively, they need
to take into account product and design
context. And this by its nature lives
outside of the code base.
It by its nature falls out of sync with
the code base over time.
And that trying to maintain a live
connection between the agent and that
context
introduces a whole set of new challenges
that we have to deal with.
Now everything I'm talking about might
seem
theoretical or you know, we're we're
still just trying to get our head around
context in the code base around skills
and how we manage skills and so on. Is
this really such a big deal at the
moment?
Well, everything I've described so far
are real challenges that I faced in my
life prior to Tessell when I was working
at Figma on the DevMode product.
Uh for those who don't know, DevMode is
a feature in Figma which allows the
designers to hand designs off to
developers. Uh human developers in this
case back in you know, back in the Stone
Age these were the tools we were using.
Um
and it gives the developer lots of great
context about the designs that they can
use in manually creating the code to
implement those designs.
And over the last couple of years, we've
seen that feature uh evolve into Figma's
MCP server, the live connection, right?
And
what we're doing here is just taking
that exact same design context, but
giving it directly to an agent via the
MCP server.
And it was in building this that we
started to see all of those problems
that I've been describing.
We would see agents picking up the
designs and doing a fantastic job in
creating front-end codes that looked
just like the design, that functioned as
the designer intended,
but the developers would look at the
code, and it would have made up a bunch
of components when they otherwise
existed, or use them in the wrong way,
or completely missed that there was a
design system that it should have been
working towards. These were real
problems that I encountered with
customers every day.
And so, we started we realized quite
quickly that we needed to find a way to
bridge that product and design context
gap with what agents were doing.
And to that end, an early feature we
started working on to address this was
Figma's Code Connect product. And here
is a tool that explicitly allowed design
system teams to connect the design
components in that design system with
their equivalent in the code base.
Now, I don't want to
go into Figma and Code Connect too much.
Um the point here is that
these aren't new problems. These were
problems over the last several years
that product teams and design teams and
devs are dealing with day-to-day
already.
We were already dealing with a product
and design context to agent harness
problem before we'd even defined half of
those terms.
Um and struggling to find the right
solution for that.
And it's
from working on that um over the last
couple of years, and now with my role at
Tesla, thinking about how those kinds of
things apply to harness engineering,
that I think there are some useful
lessons we can take from that as we
think about solutions to that problem.
The first lesson is that
in building this code connect tool, we
were aware that there was that that that
connection between product and design
context and what's in the code base
required dedicated maintenance.
In enterprises, there are entire teams
whose sole job is to make sure that that
connection is up to date and is um
makes sense and that there is
equivalence between the two.
And one of the reasons those teams exist
and that maintenance is required is
because the design context and the
product context is constantly falling
out of sync with the code base. Both are
evolving at their own pace for their own
reasons and it requires dedicated effort
to keep the two reconciled.
And one of the learnings was that
sometimes it's not desirable actually to
keep the two completely in sync. There's
an acceptance that they will of course
have to be out of sync because of the
pace of design work and product work and
dev work and so on. And it's the job of
this team just to make sure the status
quo is functional and working and to
keep track of that over time.
And I think that's broadly true not just
of design and code context but product
and design context in general.
The third lesson I think is interesting
in that as someone working in product
management on this product, I was also
very much aware of the the business and
the structural constraints around the
tools we were building.
Figma as an organization was very
protective of its design system IP. It
didn't just want to give away the keys
to the house. And so we had to be very
careful about finding the right balance
between supporting agents and the
developers using them, but also not
giving everything away and destroying
the moat that they've built over time.
And I think that's true across all of
these product and design SaaS providers,
not just Figma.
So,
as I spend my days currently thinking
about Harness engineering and how we
make sure that agents have all the
information they need to do a great job
for developers.
And I take on board these lessons that
I've learned from my experience in
trying to solve this in other
organizations,
I see maybe three directions that the
Harness can take in order to solve this.
And if we've got a bit of time, there's
a sneaky fourth one as well.
Um the first is that
we can see these tools perhaps opening
up.
And we're already seeing this. The
number of these third-party tools that
have MCP service just now is exploding.
And we're also seeing them expand with
their own APIs and CLIs and so on.
I think you still do see restrictions
and rate limits in place. And we're also
seeing
this surface being an opportunity for
those organizations to create new
monetization pathways as well. So, I
don't think the solution here is as
straightforward as the all the data will
just become available for everything.
But I do think this is going to get us
some of the way there.
Um and it's something where we're in the
middle of at the moment.
Another option is the idea that
there is an agent that sits between the
third-party product and design context
and the Harness agent.
In particular, the lesson I learned was
about this connection requiring
dedicated maintenance um and pruning
over time. And increasingly, we did see
those teams using agents to assist them.
So, it's entirely reasonable that they
start to get to a place where they can
automate a lot of that work.
And I think as we think as well about
the Harness itself acquiring its own
agent in order to build and manage that
Harness. And you know,
testel.io/agent, [clears throat]
check it out. Um
we can see the role that those kinds of
agents might have expanding to cover not
just managing the context within the
code base, but also the context that
lives outside of it as well.
And finally,
another option here is that this context
that lives outside the code base and is
unmanaged and unversioned, perhaps just
gets swallowed by the repo. And we'll
see it making inroads into it and then
being able to be managed by the harness
directly.
And I think what's interesting with this
is that
there are some challenges here,
certainly.
We're going to have to still meet
product and designers and other
non-developers where they're at
because designers are still going to
want to design on a canvas regardless of
where that data ends up living. Likewise
with CRMs and things like that.
So, we need to meet them where they're
at.
But, it could be that
there's just still so much value in
having this context within the harness
that we see an organic pull of that data
into a place where it can be managed and
versioned and evaluated and all this
great harness stuff.
I also think what's interesting about
this direction is
it also calls to the fact that
we as non-developers are increasingly
looking like developers. In fact, there
are several talks yesterday and today
specifically about this topic and about
product managers and designers and so on
creating PRs and actively contributing
to the code base. This itself might be
the impetus for us to fold the kind of
context that we're generating day by day
into the repo.
And with that in mind, what I want to do
is
go back and revisit our example from
earlier
and think about
the situation where perhaps a developer
wasn't involved in this at all.
We can imagine a PM like myself had that
conversation with a customer.
Transcribed that conversation using
Granola, fed that into Claude Co-work. I
have my own set of skills there that are
able to look through transcripts like
that and identify features from them.
Turn those features into linear tickets.
I have a skill that encodes my road map
and make sure that this fits my road map
and has the right priority.
And you know, one thing to call out here
is that
I as a non-developer might be developing
these skills outside of the code base.
These aren't versioned. These don't have
These aren't accessible to my harness.
They're not aware of them.
So,
we need to make sure that
this might be the first way way that we
bring some of that context into the code
base to manage that kind of thing.
And of course here Claude Claude Co-work
turns
the feature from the Granola transcript
into a linear ticket that then fires off
that flow from earlier. The feature gets
built and the customer's happy.
Except
what the PM didn't know is that there's
a reason this export feature was hidden
behind various settings menu because of
some architectural decision that was
made sometime in the past that made
exporting the customer's data a hugely
expensive task and therefore we didn't
want this to be something that was
widely available and operating with high
bandwidth.
This causes a PR with a huge number of
changes and all of this is invisible to
the PM. Um
who's happily tapping away on their
computer, clapping themselves on the
back for the fact that they're able to
push PRs and make features by
themselves.
Um
And what's missing here is I know
personally from my own experience in
managing technical teams, when I'm
deciding which features to work on,
I massively value the feedback and
conversation that I'm having with my
team to let me know, you know, help me
understand the technical effort that
goes into creating some of these
features.
That helps me understand the technical
debt that we might be creating as a
result of this.
And it can be just as valuable for a
product manager to know when not to
build something than to just look at a
backlog as it's to-do list that we just
need to throw agents at and work
through.
And so, another challenge here is that
so far I've been talking about bringing
product and design context to coding
agents, but we also need to think about
it this the other way around and
bringing
uh
coding context to the kind of
decision-making that's happening outside
of the codebase, but that still affects
it.
And so, one way this might evolve is,
you know, we keep talking about coding
agents and the harnesses that enable
them, but perhaps it's going to be more
like each of the different roles within
the product team will have their own
agent and their own harness and these
harnesses are going to have to talk to
each other. And maybe this is what the
solution ends up looking like.
Now, it's not clear which direction
these things are going to go in and
we're obviously going to see a lot of
progress being made on this front in the
next 6 to 12 months.
I think the thing that's clear to me is
that product and design context is
critically important for coding agents
and as we work on harnesses for coding
agents, certainly over the next couple
of months, we need to take that into
account and figure out the best way to
overcome some of the challenges that
we've talked about today.
Um I'm sure folks in this room are
actively working on this. I know I am as
well and I'm really excited to be
working in this area.
And with that, I'd like to say thank you
so much. Um been a great audience. I'm
happy to stick around and answer a few
questions.
>> [applause]
>> Awesome. Thank you very much. Uh right,
I'm going to try and these I'm going to
try and run through these tables and get
uh get the mic to people.
If anyone's got a question, please raise
your hand.
Any questions, Manny?
>> Thanks.
Thanks for the talk.
My first question comes in
if you're feeding more context
in addition to what we already feeding
in, like where do you draw the line and
how do you group them? When do you when
do you feed in a bit of context that's
needed? I remember there was some final
board activities at my workplace where
they were asking what all should be
added to the code base. So, there was
this whole wash list of things including
design and everybody wanted to get
everything in the code base because they
want to feed all of that, like you know,
Slack conversations, Teams
conversations, your email conversations
with your client. Like where do you draw
where where do you draw that line
because obviously you need context, but
then
context is king, but then which part of
it is it's it's quite subjective as
well, right?
>> Yeah. Could you share some some some of
your thoughts on that?
>> Yeah. It's, you know,
where do you draw the line in terms of
adding context to the agent when I'm
advocating not just for adding code base
context, but also product and design
context, which is is is likely even
larger than what's in the code base.
I mean, I think this is the core problem
of context engineering and harness
engineering in general. Even if we just
remove the product and design context
question for now, it's already a huge
challenge to figure out how to encode
all of the context that might live
within a repo and its architecture and
its norms and so on into something
succinct enough that's relevant enough
for the agent
to do the the right job. And part of the
reason we are setting up things like
evaluation architectures and so on is so
that we can actively work to get that
context down into just the right size,
but also make sure that that context is
actually doing a good job to evaluate
and so on.
We're going to have the exact same
problem, I think with product and design
context. In fact, that makes it harder
because it's I think as I've said today,
by its virtue, it's messier, there's
more of it, it's in lots of different
places. And so,
I think we just need to well, for now we
need to apply the same kind of tools. We
need to figure out which design context
is signal versus noise, and perhaps have
agents to help us decipher that. We need
to shrink that down into formats that
are succinct enough to either live as
skills in the code base, or maybe
there's some other methodology that we
shrink this to, and have that be
accessible to the agent. And then we
need a set of evals to make sure that
the agent is actually being boosted by
that context and isn't being
overwhelmed. So, the the short answer is
I think we need to apply all the same
principles with code base context to
product and design context with that
extra layer of difficulty that comes
with that because of it being external.
>> Trial and error and evaluation.
>> Trial and error and evaluation, that's
exactly
>> Also, we've probably got time for one
more question if there's any other
questions in the room.
If not, thank you very much. Please give
it up for [music] Mark again.
>> [music]
--- TRANSCRIPT END ---
