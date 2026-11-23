<!-- transcript_hash: sha256-75acdb546a3e1602 -->
# Summarise this video transcript

You are given the FULL transcript of a YouTube video. The transcript comes from YouTube's own
captions, so it may contain caption mistakes, filler words ("you know", repeated words),
`[music]` tags and `>>` speaker-change markers.

**Video:** How Bitcoin Survives Quantum Computers (ft. Dan Boneh)
**Source:** https://www.youtube.com/watch?v=E61gUCKcx2s

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

Save your answer as: `kb/highlights/How Bitcoin Survives Quantum Computers (ft. Dan Boneh) [E61gUCKcx2s].md`

--- TRANSCRIPT START ---
All right. So, always a great week at
A6Z crypto when Dan Benet comes and
visits. Uh, so legendary cryptographer,
longtime Stanford professor, mentor to
hundreds of people in the crypto space I
would say and as always talking about
something super super timely and
relevant postquantum signatures. Dan,
>> awesome. Thank you. Thank you, Tim. And
uh always a pleasure to visit the lab.
For those of you watching the video, uh
this lab is phen phenomenal. If you have
an opportunity to visit the lab, you
should jump on it and uh take any chance
you get to visit this place. Okay. So,
uh today I wanted to talk about uh
basically this question of postquantum
signatures uh for for blockchains. The
talk is going to have uh two parts to
it. Uh the part that's uh that's new is
going to is joint work with uh Benedict
uh Justin D from local host uh Yavore
and uh Camila. Okay. So uh what is the
problem? The problem is uh every week
when I look up uh various news about uh
blockchains, there are constantly news
uh about the quantum the quantum looming
threats to uh the blockchain ecosystem.
So you know bitcoin is going to end. Uh
Jim Kramer is selling all of his
bitcoins because of quantum. Um D-Wave
says, you know, quantum computing uh
they're gonna, you know, all the proof
of work stuff is gonna is going to be
destroyed. So basically, and by the way,
these are just uh from the last week.
This is not like stuff that I I fished
around for. This is like uh stuff that's
coming up every every week. There's all
these uh messages about how uh you know,
how um blockchains are going to uh end
up once uh Qday arrives. So the issue is
that of course systems like bitcoin need
an answer for this and other blockchains
need an answer too uh in that they need
to become somehow uh postquantum. So the
community is not asleep at the wheel and
in fact there are lots of postquantum
signatures that are being developed. Uh
so here I wrote a couple of the families
of uh postquantum signatures. There are
lattice based signatures there are
hashbased signatures. There are isogyny
based signatures. There are multivariate
based signatures and then there are
signatures based on zk proofs of
pre-image. So all of these are being
considered for standardization. Um uh
yeah and so the question is which ones
should uh blockchains use. So for many
months for many years uh I've been
advocating for uh lattisbased signatures
to be used in a blockchain space mainly
because blockchains need the algebraic
structure that traditionally comes from
ECDSA and Schnore. Uh but uh you know we
need uh the al this algebraic structure
and much of it is also a available in
the in the lattice space. Yeah. So I've
been advocating uh for lattice based
signatures for uh blockchains but
unfortunately I don't think that's uh
that's where the world is going. Um part
of the reason for why that's not where
the world is going is because of this
fear of assumptions and what happened
with hawk for example is exactly working
against us in making the argument for uh
lattisbased signatures for blockchains.
So currently the most likely uh way
things will go at least for Bitcoin and
Ethereum are hashbased signatures and I
listed a couple of hashbased signatures
that are being considered for these
systems. And one of the reasons there uh
they're probably the way Bitcoin and
Ethereum will go is because exactly
there are no new assumptions that are
introduced into the space because of
these hashbased systems. Not only that,
the Bitcoin community in particular,
they're quite h quite excited and quite
happy to remove the discrete log
assumption that's currently uh used in
Bitcoin, namely for ECDSA and for
Schnore. And by using a hashbased
signature, the only assumption in
Bitcoin will be shot to 256. And I get I
have to tell you when I talk to the
Bitcoin core developers about using
lattis based crypto, it's just not
working. And so mostly this is probably
this is kind of uh going to be the way
uh things are going to go. And so since
hashbased signatures are going to uh
play such an important role in the
future of blockchains, I wanted to spend
the first half of the lecture actually
just kind of giving you a crash course
uh in hashbased signatures and uh where
things are going, how they work and then
in the second half we'll talk about the
new results. Sound good? Okay. So that's
the plan. So uh so let's talk a little
bit about hashbased signatures. The
first thing we have to talk about is the
terminology that's being used in the
space. And so let me throw a couple of
uh terms at you just so you you become
comfortable with them. So the first term
is what's called a one-time signature.
And we have many examples of one-time
signatures. The idea behind one-time
signatures is they're secure as long as
you issue at most one signature you
under a single public key. So you sign
something then you have to replace your
public key. You sign something again you
have to replace your public key. Uh the
these things these signatures actually
become insecure if you happen to sign
two messages using the same public key.
The nice thing about these onetime
signatures is we get relatively short
signatures. So here I wrote up one
example only 292 bytes which is actually
uh pretty cool. Uh it turns out uh this
particular parameters causes the
verification to be a little slow. So
what people tend to use is a little
longer signature uh that has a faster
verification procedure. And so these are
kind of the parameters for onetime
signatures. The next term uh to be
familiar familiar with is what are
called few time signatures. So few time
signatures basically they're secure as
long as you use a public key or a secret
key rather uh to sign only at most a few
messages. The more messages you sign the
less secure the system becomes. Yeah. So
kind of security degrades uh the more
you sign. And I gave you one example
here. Here's like a just one example of
a signature length in this in this uh
space. Um and you can see here if you
only sign one message you have like
pretty good security. If you happen to
sign two messages security starts to
degrade. And you can see that it
degrades uh the more signatures you
issue under a s a single public key. And
this is by the way just one example. You
can reparameterize the scheme to support
10 signatures to support 100 signatures
at the 128 bit level. The signature will
become a little bit bigger. And again if
you exceed the say the 10 signature
limit all that will happen is security
will security will gradually deg degrade
until you get to a point where it's no
longer secure. These are signatures that
are called like horse and fours and
fours is a very common uh uh uh way to
do this but all of them I should say use
a very similar idea. They're all kind of
have they structur structurally very
very very similar and we'll talk about
them in a bit later. Okay. So those are
few time signatures. The last
terminology I wanted to introduce is
what are called stateful uh few time
signatures. So stateful few time
signatures is kind of the almost obvious
thing to do which is basically you take
a couple of one-time signatures and you
string them together. Basically you put
them all in a Merkel tree and then you
can sign one message using one each leaf
of this Merkel tree. Yeah. And so here
again you get very short signatures
which is kind of a benefit. You can sign
a thousand messages. If you string
together a thousand one-time signature
public keys you get very short
signatures. So very this is very
attractive to people. It's also very
fast to verify those signatures. The
problem of course is now you have one
public key that represents a thousand
one-time signature public keys. Now you
have to remember which public key you've
already used to sign a single message.
So this is why we call them stateful. In
particular, you have to maintain a
counter that tells you how many messages
you've already signed and that tells you
what what is the next leaf uh to use.
Yeah. So the signer has to maintain uh
the state to make sure each public key
uh is used only once. The danger with
this of course is that somehow you fail
to update your your your state. Uh and
we call this kind of a big foot gun.
Yeah, this is quite dangerous to use. If
you ever fail to update your state or
maybe you have multiple devices um and
they go out of sync in terms of the
state uh that they use and you ever end
up signing two sign two messages under
the same leaf uh you'll basically um
compromise your signature scheme. And so
because this is such such a dangerous
thing to use the thing that I want
everybody to remember is if you're going
to use a stateful signature please
please please use a hybrid signature
scheme where you use both one of these
stateful schemes combined with ECDSA.
Yeah. So until Qday happens, even if you
make a mistake, the ECDSA component will
keep you safe. Yeah. So I want people to
kind of get into this mindset. If we're
going to deploy stateful signatures, we
have to use um a hybrid scheme. So at
least we're protected until until QA.
Okay, good. Qday is when quantum will
eventually appear. Yeah.
>> The fact that there's a long private
key, that's that doesn't worry you or
>> the fact that there's a long private
key. Uh no, the private key is very
short. The private key is all generated
from a seed uh using using a PRF. Yeah.
So both the public key and the private
key are very short in these systems.
Yeah. So there's no no issue here. And
you don't even have to store two to the
10 secret keys. You just generate them
on the fly. So if you want to use leaf
number seven, you just on the fly you
generate the secret key for leaf number
seven and you sign.
>> I see. So then you have like some Okay.
You could get forward security if you
don't do that. But
>> yeah, this is but okay. No, no, there's
no forward security is off the table
here. So yeah, but this idea that you
can generate uh leaves on the fly is
very important. In fact, thank you for
asking because uh that's exactly what
happens in the NIST standard. So NIST
actually put up a standard called
SLHDSA. It's based on a framework uh
called Sphinx Plus. Um I kind of drew
the picture of uh SLHDSA here, but
honestly I can't explain to you in two
sentences how uh this picture works. So
I'm going to explain to you in more than
two sentences how it works. But I do
want you to understand how the Sphinx
framework works because it's it's
starting to play a fairly important role
in the industry. Okay. So the the NIST
standard basically is designed for 2 to
the 64 stateless signatures. Yeah. So
you don't it's a regular signature
scheme. You don't have to maintain any
state and it's secure as long as you
issue it at most two to the four to the
64 signatures under a single public key.
2 to the 64 is a pretty big number. Yes.
Uh as a result you can see the
signatures are pretty big. So uh uh the
regular mechanism is generates 8
kilobyte signatures there. If you want a
fast serer the signature become even
bigger. One thing to remember is the
public key is always short in these
signatures. Yeah. And in fact the public
key the way you verify these signatures
is you rederive the public key from the
signature. Yeah. And then you verify
that the public key is that you got from
the signature is really the thing that
you recorded as the public key. Okay. So
I want you to remember public keys and
secret keys are very short in these
systems. And the way you verify a
signature is you use the signature to
derive the public key and you check that
you got the correct public key. These uh
signatures are actually very well suited
for a software update system which is
what we wanted them for. Yeah. So that
we want a signature scheme that's like
robust and can and uh based on rock
solid assumptions. Uh so that our
software update systems are for sure
going to be uh secure. And in fact in a
software update system the length of the
signature doesn't matter so much because
I'm anyhow sending you sending you
megabytes of data. But it's very poorly
designed for a blockchain, right? We
can't put a 8 kilobyte signature uh for
every transaction. Uh it's just too
long. And also to be honest, we don't
need a signature scheme that can support
2 to 64 uh signatures because we don't
issue 2 to the 64 transactions. So NIST
got a lot of complaints about this. And
just in April this year, they put down a
scaledown version of Sphinx uh which
only is designed to support 2 to the 24
signatures. You can see the signature is
actually much shorter, only 3.8 8
kilobytes, but again it has a lower
bound on uh on on how many signatures
you can issue. They were really obsessed
with getting as short a signature as
possible. And so just uh to tell you um
the signing time here is actually quite
bad. It takes about a billion hashes
because of the design of the scheme.
Takes about a billion hashes to generate
a signature. Uh normally it would be in
the millions of hashes. Here it's a
billion hashes to generate a signature.
The cool thing is verification time is
very short. It's just 300 uh 300 hashes.
This is actually very exciting to people
who want to do ZK snarks on top of these
signatures because to build to um snark
the verifier, you only have to verify
300 uh 300 hashes.
>> Yeah.
>> So is there 1 billion hashes because it
needs to recreate the whole tree at the
time of signing if
>> not the whole not the whole tree. What
it does is uh there is actually you're
right there is a single tree with two to
two to the 24 leaves and what it does is
it recreates kind of uh well we'll talk
about this in just a second. uh the it
recreates part the part of the leaves uh
for generating the signature. Yeah. And
that actually is exactly where all the
time comes from. Cool. Yeah. Please.
>> Uh do you have any intuition of the
relationship or if we go even lower than
2 to the 24th how much the signature
size can shrink?
>> Yeah. Yeah. Actually, in fact, there are
lower parameterizations. Uh huh. I'm
funny that you asked that. Uh well, if
you want if you if you really want to
see, I'll tell you lower
parameterizations. Uh so for example, if
you want to do two to the two to the two
two to the 14 signatures, you can go to
I mean here it's 3.9. Uh but it does so
it doesn't shrink too much. Yeah. Uh I
mean there again there are lots of uh um
issues here. The reason it didn't shrink
too much is because you notice uh this
is a much faster signer than what uh
NIST uh proposed. You can even get even
faster signers if you allow the
signatures to grow. So there's there's
like six knobs that you can turn in
these schemes and they determine the
size of the signature, the time to sign,
the time to verify. There's lots of
parameters to play with here.
>> Yeah. Yeah. Good. It's a good it's a
good question. Uh okay. So um I because
again because these signatures are going
to start to play such an important role
in the industry, I wanted to just give
you a crash course in how uh Sphinx or
how SLHDSA actually works.
>> Okay. In terms of all the knobs, there's
still like there isn't a knob that goes
the opposite direction.
>> Which opposite direction?
>> Very expensive to verify, but but cheap
to sign.
>> There is. Yeah.
>> For this,
>> yeah, you can actually shrink the
signature if you allow the verifier to
uh to work even harder.
>> Flip the flip these parameters.
>> I mean, not exactly flip. There's
complicated parameters, but you can
shrink the signatures if you allow the
verifier to work even harder. Yeah.
You'd allow the signer and the verifier
to work harder. Yeah. Yeah. There's uh
lots of parameters here. Yeah. In fact,
it's uh I can tell you well, you'll see
why in just a second. Uh but the it's
it's it's um tricky enough to set all
the parameters that there's actually a
script that tells you you tell it the
parameters and it tells you what
security level you have. Yeah. So, yeah,
this is now a little community devoted
to kind of playing with the various
parameters for the schemes. But let me
show you how how they actually work.
Yeah. So, I think it's because they're
going to play such an important role, I
want to make sure people understand uh
what the structure looks like. So in uh
in SLHDSA or like I said in the frost
framework when you generate a key uh
what you start off is by generating
basically kind of a Merkel tree. It's
called an XMSS tree for a technical
reason but really it's kind of a Merkel
tree of um of a bunch of one-time
signature public keys. Yes. So each one
of these leaves can only sign one
message and you generate a relatively
small number of them. Let's say 512 uh
in SLHs GSA. Okay. So now the qu and the
what is you should ask what is the
secret key? Well um the secret keys that
I was saying is basically uh just a a
pseudo run function secret key that can
be used to generate all the secret keys
in the system. So the secret key you can
see the public key is very short. It's
just a Merkel root and the secret key is
very short uh as well. Great. So now we
have 512 one-time secret keys. What do
we do with these onetime secret keys?
And the answer is we do the same. We
just do this this over and over. So uh
what these uh public keys will actually
be signing are actually more uh more uh
trees of this size, right? So what you
would do is each one so you generate 512
a leaf containing 512 signatures and the
Merkel root of that leaf is the only
message that this leaf will ever sign.
Okay, so you can kind of start to expand
the number of leaves here by basically
having one each one-time public key sign
one route of many more onetime public
keys. And you do that over and over and
over again until you end up with enough
leaves. In particular, in SLHDSA, you
would do this over and over again until
you end up with two to the 64 uh
different leaves. Okay, now 2 to the 64
is a huge tree. You never want to
actually develop this entire tree. So I
call this a virtual tree. I call this a
virtual tree because you never actually
write it down. Yeah. It's just when you
want to sign you develop one particular
path in this tree. Yeah. And you then
the rest of the tree is virtual. It's
never actually materialized anywhere uh
in the system. Uh so we have this
virtual tree with let's say 2 to the 64
uh possible leaves. And then when you
want to sign them oh sorry there there's
a bit more that's being generated. So
all of these are just each leave is just
a onetime secret key. Yeah. Onetime
secret key. The only thing only thing
these leaves are going to sign are other
public keys for what we call a few time
signature. Yeah. So these are stateless
few time signatures. Stateless few time
signatures. Okay. And so uh the only
thing that the leaves of the virtual
tree will sign are the public keys of
these FTS's. You see so inside the tree
every public key is used to sign exactly
one message and the leaves can actually
sign a small number of messages in a
stateless fashion. And again, these FTS
uh uh secret keys and public keys are
never materialized explicitly. They're
only materialized as you need to use
them. So now let's talk about how
signing works. So far so good.
Everybody's with me. You can see how the
structure works. Yeah.
>> Maybe just one question. How do you how
do you ensure that you never exceed the
threshold of a few times?
>> Amazing question. I'll come back to that
in just a second. Perfect question. So
let's talk about how signing works. I
have to explain how signing works and
then we can talk about how not to
exceed. Exactly. So how does signing
work? Well, when you want to sign a
message, uh what you do is you choose a
random leaf. Yeah. Uh you derive using
your secret key. You derive the secret
key and the public key for this leaf.
You sign this leaf. Oh, you sign the
message using this few time signature.
And then you can you kind of do the
obvious thing. Yeah, you kind of sign
the public key of the few time signature
using the one-time signature that's at
the leaf. And then you know you have an
authentication path throughout the tree
that's connected all the way back to the
public key. A signature here on a
message is basically going to be the
authentication path to the leaf. The
one-time signature on the public key the
few time signature of the public key.
And then the few time signature is used
to actually sign the message M1. Okay.
So that's the whole uh that's the whole
signature. So if you want to sign
another message, you do the same thing.
You pick another leaf and uh you do
exactly the same thing. Yeah. you you
kind of generate uh this authentication
path and so on. Okay. So now you uh
imagine we have already signed n
signatures. Literally what happens here
is this is like literally a bins and
balls experiment, right? So when you uh
sign them basically you kind of throw in
balls into different uh leaves and you
end up with literally a classic bins and
balls experiment. And for security we
want to make sure that the overall
forger forgery probability should be
less than 128 bits. you know 12 to the 2
to the 2 to theus 128 again like I said
this is a complicated script uh to uh to
work out exactly what the probability is
but in particular what we what we need
to do is to make sure that no FTS scheme
has too many balls in its bin okay so uh
you do the calculation and you make sure
that basically you know this probability
is less than half to the 128 and that's
kind of where security of the scheme
comes from yeah so when you play with
these parameters uh these parameters are
literally kind of doing these ball bins
and balls experiments uh to make sure we
don't use each leaf too many times.
Yeah. So that I hope that answers your
question. Yeah. Yeah. Please.
>> Like why don't you just go left to
right? Like why are you randomly picking
leaves to use?
>> Uh yeah. So this needs to be a state so
these schemes are stateless signature
schemes. Yeah. If you were going left to
right, you would have to keep state. The
whole point here is this has to be a
stateless scheme. And by the way, this
is a really great question. um uh you
know we have lots of hasht data
structures that aim at minimizing this
accumulation at one point right if you
throw n bin n end balls into n bins
you're going to have one bin with login
balls right and we have like you know
double hashing cuckoo hashing we've
developed lots of techniques for trying
to kind of minimize the most loaded uh
bin if we had a way to do that in a
stateless fashion that would directly
improve SLHDSA yeah so there's a
fantastic question here uh in a
stateless fashion. Could you kind of
could you choose your bins so that we
don't get we we we don't get the worst
case balls in in in every bin? Yeah. So,
probably not. But it's a nice nice
question if this can be done in a
stateless way. Yeah. It's a good good
question for uh data structure folks.
So, that's kind of the mechanism that
goes into uh into uh uh Sphinx plus and
SLHDSA. Uh with that I want to shift
gears and talk a little bit about how
what the plan is for using this in
Ethereum and uh more importantly in
Bitcoin. In Ethereum the system is
called leanig. In Bitcoin this is called
shrinks. Uh the Ethereum system is a bit
under flux. So unfortunately I chose to
explain this using Ethereum because more
people here maybe are familiar with
that. Um but the shrinks system is
literally getting codified in Bitcoin.
Uh and so that's probably how things are
going to work. So the the idea behind uh
shrinks is basically to generate two
types of keys. Yeah. So the first type
of key is going to be a long-term uh uh
stateless uh public key, stateless
signature scheme. It's kind of again a
scaled down version of SLHDSA that say
will support up to a million signatures.
Yeah. So we have this long-term public
key that we derive from our seed phrase.
And then there's a there's a second key
that's supposed to be much shorter term.
Yeah. And ideally, this second key will
only be used to sign a single
transaction. Yeah. And we're going to
change it on every transaction. So here
you notice we use a seed phrase, we use
the wallet ID, and importantly, we use a
stateful counter to generate the secret
key. Yeah. And as I'll see I'll say in a
few seconds, we're going to actually use
like a few time signature for safety.
But really, you can think of this as a
one-time signature. So at least the plan
back in June like what is it a month and
a half ago in uh in Ethereum was to use
to use a stateless uh few time
signature. That plan might be changing
now in Ethereum but in shrinks they
really like the the short signature that
you get from stateful signature schemes.
So shrinks is really going with stateful
FTS. They're going with these XMSS trees
that I was just telling you about. Yeah.
So again, keep in mind in Bitcoin, uh
the current plan or at least what's
being proposed is to use uh two keys.
One long-term stateful stateful one
long-term stateless key and one uh
stateful key that generates much much
shorter signatures, but you do need to
maintain state in order to make sure you
don't you never use a leaf more than
once. Yeah. And so again, I explained
this using Ethereum just because I think
it's easier for people to understand how
it works. In Bitcoin, there's extra
complications. Uh, but really what we're
going to do is we're going to initialize
an account abstraction contract. In the
contract, we're going to write our
long-term key and our short-term key.
And the goal is that the short-term key
is again only used to sign a single
transaction. So, under normal use,
>> Dan, so what do you use the long-term
key for?
>> Hold on. Excellent question. You guys
are asking fantastic questions, but it's
on the next slide. Yeah. Uh, so the
short-term key supposedly under normal
use, that's the only one that's used.
And again, the idea is every time you
sign an Ethereum transaction, your
transaction, you know, the call data for
your transaction is going to end with a
public key for the next transaction.
Yeah. So, you sign you you use your
public key to sign one transaction and
then you replace the onetime SE
signature, the onetime public key. So,
the next transaction uses a different
public key and kind of it keeps on
rolling like this forever. And the cool
the cool thing about that is we end up
with uh short signatures on the on the
different transactions. But then we also
have the long-term key and the long-term
key is going to be used for recovery. So
the question is what happens if your
wallet blows up and you lost your short
short-term key? More important than the
real problem is what happens if you lose
your wallet ID and more importantly you
lose your counter. Yeah. If you ever
ever have any um uh any uh uh uh lack of
confidence about the state of your
counter, stop using it and then you use
your long-term key to re to reinitialize
the short-term key chain. That's kind of
the the idea and that's what I what I
say here. So the contract code basically
will update the short-term key from the
cold data. Yeah. So every time we update
the short-term short-term key and the
next transaction will be authenticated
with that. Um the reason we we want to
use a few time signature uh for the
short-term key even though it's it's
really going to be used only to sign one
transaction, the reason we want to say
support five or 10 uh signatures on it
is again if you have an accidental reuse
of a of a state, you're not going to
shoot yourself in the foot. So if you
have accidentally use the same state 10
times, you have a problem. Yeah. But if
you just use it two or three or four
times, you're still you're still secure.
So this is kind of why uh they're going
uh they're going for that. And yes, yes.
Again, this is a foot gun, right?
Because if you use your key more than 10
times, you have a problem. So, please,
please, please, anyone who's listening
on the video, if you're gonna deploy
anything that has states, I'm going to
say it again and again and again, please
use a hybrid signature so that at least
until Qday, we're not harming anyone
because the ECDSA component will protect
us from this foot.
>> Yeah. Could you could you just put the
uh counter along with the uh next public
key in the call data?
Uh yes. Uh but then what
the problem is?
>> Well, but then how how do how does how
is the how does the wallet know that
you're providing the latest state of the
chain, right? Maybe you provide maybe
you're providing to the wallet like a
previous block that has an old value of
the counter.
Yeah. And then you this wallet will end
up signing twice with the same counter.
>> At least it pushes you gives you some
lower bound. What was
>> Yeah. Yeah. Yeah. Of course. Of course
this is a good idea. Yeah, I mean I I I
I think I oversimplified. Of course, the
counter appears here, but it's not
something that the wallet can rely on.
Yeah, the wallet needs to rely on the
state that it stores it stores locally.
It's a good it's a good good point,
though.
>> It's a bit of an aside. Um
>> Oh,
>> but because it so the your your warning
is if you're going to use a stateful
signature, do it hybrid. Um there's this
situation uh I think is quite bad where
uh for national security systems the NSA
uh will not let you use uh stateless
hashing signatures and also uh basically
won't let you use hybrid signatures. So
if you want to use hashing signatures
you're stuck with uh stateful
non-hybrid. And I take it from uh what
you're saying here that you think that's
bad. But if the rest of society's
infrastructure moves to something that
has certain risks, um,
>> you know,
>> what's the point?
>> No, no, that's a little bit different.
Okay. So, maybe this is a discussion for
for later on, but uh the internet like
protecting TLS, that is a very different
question than protecting blockchains.
Yeah. So TLS for example for uh
confidentiality, most TLS connections
are already postquantum secure. The only
issue is what to do with certificates
and the internet community has come up
with its own solution to the fact that
hashbased signatures or even lattice
based signatures are problematic. These
are called Merkel tree certificates. Um
and so the internet is kind of has its
own set of solutions to these post the
you know the fact that postquantum
signatures are a little problematic to
use. Uh but that's I think very
orthogonal to what uh the blockchain
community is doing. Yeah, it's a it's a
good point. It's a you know uh the story
here is uh not just technical it's also
kind of political and so on. Um but yeah
and there are many moving parts like the
internet but for um for now we're just
focusing on the blockchain space where
we can design whatever whatever it is we
need. Yeah but it's a good it's a it's a
good point. Thanks Justin. Um okay so so
far so good so everybody understands
this dual uh oh yeah this dual idea that
like under normal use we'll just use a
short stateful uh uh one time or few
time signatures and if we lose our state
or somehow we don't trust the state that
we have then we just reinitialize things
using the long-term key. So the
long-term key is only kind of used uh in
a case of emergency and you notice if
you look at the uh diagram the long-term
key is only derived from the seed phrase
whereas a short-term key you need to
have the states and more importantly you
have to have the wallet ID. By the way
the reason I put the chain ID in there
too is you want different uh short-term
um chains on different uh on different
blockchains. Okay, cool. So uh yeah, so
I think this is just basically repeating
what I just said. So on the wallet uh at
initialization time you would generate a
random wallet ID uh that gen that
initializes the short-term chain and
then the counter is updated on every
transaction uh and so everything should
work normally until you lose your uh
your wallet and then you reinitialize
using your seed phrase. One complication
by the way is if you have a lot of
wallets on a lot of chains these
hardware wallets might actually run out
of space, right? So they don't have that
much nonvolatile memory. Uh so they
might run out of space uh which which is
kind of a headache for these uh wallets
because now they have to offload their
state to the laptop. Yeah. But they
can't just offload to the laptop uh for
the same reason that we heard before
because how do you know the laptop might
provide uh the wrong state. So now the
wallet would have to kind of maintain um
a counter to make sure that whatever
comes back from the wallet is uh is
fresh. So it's a bit of a engineering uh
headache but we it can be done. Yeah.
that uh there's some development to do
here. So generally the wallet uh um
companies they actually are quite
fearful of these stateful signatures
just because of the headache it's going
to cause for them. I think we know how
they would build things but it is going
to take some work on on their part. So
if you talk to uh you know to ledger and
treasure and all those they are also
quite opposed to hashbased signatures.
Yeah. Which is kind of interesting. Um,
one of the I can say one of the
arguments they give today is hashbased
signatures are very slow on the current
ledger. There they take it takes uh many
tens of seconds to generate a key and to
generate a signature. Um, uh, but that
actually is going to get solved once
they move to a future processor that
actually supports SHA 256 built in.
Yeah. So with hardware acceleration
hopefully running times will be normal.
Yeah, I may have missed something, but
does it mean that now recovering your
Ledger wallet for instance from the seat
phrase, you can only do it a few times
because of the use of that special
stateless key?
>> Well, the stateless key is initialized
for like two to the 20 times. So, you
can do it like a million times is good.
You know, hopefully you don't have you
don't have to recover more than a
million times. You know, you got other
problems if you need to do recovery more
than a million times.
>> Yeah. So, that that's where that number
comes from. In fact, people want to
scale that down even more, like maybe
even two to the 14, not two to the 20,
cuz you're not going to be doing
recovery that often.
>> As you see, as you get close to the
upper limit of if you do need to recover
a huge number of times. Exactly. You can
resign, you can use the the last
transaction on the old key to refresh
the the new launch,
>> right? But that may change your seat
phrase, which is the thing you put in
the bank. No.
>> Yeah. Yeah. Then you have to change
Yeah. Then you have to to change your
seed phrase. And of course, that's uh
that's that's on you. But that hap that
hopefully that happens so rarely it's
probably a good idea to change the seed
phrase regardless uh that that
infrequently.
>> But also this idea of putting state on
the blockchain might be useful, right?
Because then your wallet could basically
say like could say I'm I'm only going to
do the transaction make sure it's on
it's on train.
>> Yeah.
>> My my state.
>> Yeah. Yeah. For sure. For sure. No, I
agree. It's a definitely a good idea,
but we don't want to rely just on that.
I mean the wallet does want to maintain
its own state as well.
>> Yeah. For exactly the freshness issues.
So that's uh my crash course in kind of
where where things are headed. Uh
hopefully this is useful because again
these things are this is like where
we're going. So these things are going
to play a pretty important role in the
coming years in uh in Bitcoin and
Ethereum. So u uh it's good for people
to know how they work. Okay. So the next
question to ask is well now that we're
stuck with these hashbased signatures by
the way some things we have to give up
on. Yeah. So for example um in uh what's
called hardened key derivation in HD
wallets that specifically uses the
algebra of public keys of shnore and
ECDA ECD DSA public keys. This is where
you can use uh you can derive one public
key from from another that goes away
with hashbased signatures. Yeah. So we
have to give up on hardened key
derivation. Uh just fundamentally not
possible with uh with hashbased
signatures. for lattice based
signatures. There are some proposals for
for hardened key derivation. So again,
that's an argument for lattice based
signatures. But uh this is where we're
going. So the other property is what
about threshold signing? Yeah. So
suppose we want to support threshold
signatures. How do we do that in in uh
using hashbased signatures? And that's
actually what I wanted to talk about.
All right. So just to remind you, the
way threshold signing works is let's say
we have a trusted setup that generates a
public key and generates something
called a CPK, a combiner's public key.
So two public keys, one for the
verifier, one for the combiner. Um and
then when you want to and then it issues
secret keys for the different signers.
When you want to issue a signature, uh
the message is sent to the signers. Some
of the signers respond. uh the com if
enough signers respond the combiner can
combine the responses and generates the
signature and again I want to remind you
the combiner when it combines the
responses it uses the combiner's public
key this uh the CPK okay which is
different from the verifier's public key
all right so the question is how do we
do hashbased threshold signatures and so
the first thing that comes to mind is
just generic solutions yeah so well what
do we have we have multi-signing right
where the way you do threshold
signatures is you generate n public keys
and you ask T people to sign uh and you
accept the signature if you have enough
if in fact you have t signatures in the
transaction. The problem of course is
this results in very large signature in
very large signatures you know
proportional to t and to me what's bo
what bothers me is that it also exposes
this value t publicly so you know people
know exactly how many keys they have to
compromise in order to uh to affect the
key yeah also in some sense with
multisig the other thing that I want to
kind of stress is in my mind threshold
signatures whether I thresholdize my key
or not is nobody's business yeah the
signature that I generate should be
exactly the same whether my key is
centralized or whether it's
thresholdized. Yeah. Uh multi-
signatures fundamentally gives you a
different signature when you choose to
thresholdize your key. And to me that
actually is seems like the kind of not
the way to go. Yeah. We want to make it
so that it's only my business to uh
thresholdize my key. Uh so one way to
deal with a large signatures is to
snarkify these two signatures into a
single uh snark proof. The problem of
course is then now the blockchain itself
has to verify snark proofs again in the
Bitcoin world this is like a
non-starter. Yeah. For them to enshrine
snark verification into Bitcoin they
have a heart attack when you when you
ask them about this. Who knows maybe
that will change in many decades but
right now it's kind of a it's kind of a
non-starter in the community. So other
approaches I I wanted to mention is uh
so for example we have this universal
thresholdizer that will take any
signature and thresholdize it in a way
that the final signature is a regular
signature non- threshold signature. This
is based on FHE. So this works great.
It's only one round you know um but
because you have to run the signing
procedure inside of FHE it's currently
slow. So if FHE systems become faster,
this will become uh practical and this
would solve all of our threshold
signature problems. Yeah. Uh today we're
not there. Uh this is too slow to use in
the real world. And of course you can
use generic MPC. Same properties as a
universal thresholdizers, but MPC
unfortunately is also a bit slow
especially for these hashbased
signatures. Okay. So the question is can
we can we do better? And in fact there
has been some work on uh doing things
better. There's work by uh Condi um yeah
but by Kelsey Lang and Lux uh from last
year called Haststack that tries to
thresholdize uh at least uh winter
signatures these onetime signatures. But
the issue with them is again this only
works when n choose t is small. They
have a different public key for every
coalition. So n choose t has to be
relatively small. Again t is revealed
and the and the threshold signature has
a very specialized format than a non-
threshold signature. There's even a
negative result uh that says that pure
threshold signatures have to be
inefficient in some sense but um I want
to I won't get into that here. So I want
to tell you about our approach which is
a different way of thresholdizing
hashbased signatures. And so here what
we're going to do is uh a little
unusual. Yeah. So the signature scheme
that we use is going to be a pure
hashbased signature. So the blockchain
will only verify hashbased signatures.
However, when we Yes. So the final
signature is going to be a standard
halfbase signatures just like if the key
was non thresholdized. However, uh the
threshold mechanism is going to be
lattis based. Okay. So again it's my
business how I thresholdize my key and
so I choose to thresholdize my key using
a lattice based mechanism. Uh so it
depends on lattice assumptions but the
blockchain is completely unaware of
lattises. Yeah. So I use lattises to
thresholdize the the the uh hashbased
key but the the chain doesn't care.
Yeah. So that's kind of the the point.
Yeah.
>> Um assuming that the latis assumptions
go wrong, do you lose your private key
or is it just that the signature is not
verifiable?
>> No, you would lose your private key.
Yeah. So it's your choice as the private
key holder. You choose to thresholdize
uh using lattises. Uh and then you know
you're subject to lattice assumptions.
Uh but at least you but the benefit is
you'll get a threshold signature that
generates regular hashbased signatures
and it supports a large N&T. Yeah. So
kind of that's that's the point.
Remember the n choose t problem simply
does not come up in the lattice world.
So the trick I want you to remember yeah
is the signature is fully hashbased. The
threshold mechanism is lattice based. So
I'm hoping that that kind of uh hybrid
is something that the bitcoin world will
be willing to swallow. And in fact that
is really not up to them because again I
as the keyh holder decide how to
thresholdize my own key. So if I choose
to use lattises, nobody can prevent me
from from doing that. Yeah. So the in
particular, you know, fire blocks and
those guys could choose uh a lisbased
mechanism and nobody can prevent them
from doing that. So if you're wondering
what prawn stands for, the pre the
shrinks, there's a variant of shrinks
called shrimps. And so I guess uh the
goal is to continue with a seafood uh
metaphor. Um but it does mean something
magically. All right. So uh so how does
it work? Oh, yeah. Yeah. So I'm going to
start first of all with explaining how
to thresholdize one-time hashbased
signatures. And so the first thing we
have to do is we have to ask well what
does it mean for what does it mean to
thresholdize a onetime signature? And it
turns out there's like problems in defi
even defining what is a threshold
onetime signature. So let me show you
the issue. Imagine the following
situation. So let's say we have a three
out of eight uh scheme. And now what the
adversary could do is he could go to
these three servers and say hey please
sign M1 for me. And the adversary can
then go to these three server and say
servers and say hey please sign M2 for
me. Yeah. In a regular threshold scheme
the signers don't normally interact with
one another. Yeah. And so actually in
fact they just do their job on their
own. They verify that the message is
okay to sign but they don't talk to
anybody else if they think the message
is okay to sign. So in this case you can
see the problem. Now we have uh two
signatures on two different messages
under the same public key and the secret
key is compromised. Yeah. So already you
notice that thresholdizing a onetime
signature immediately runs into
problems. So one solution of course is
to say ah well the signers now have to
coordinate to make sure that when these
three signers sign M1 they tell the
other signers don't ever sign anything
else under this public key. Yeah. But
that coordination Yeah. So it seems
problematic. I mean in particular it
seems like it requires a whole
blockchain just for that. Yeah. And so
the question is can we do threshold
onetime signatures without coordination?
And so let's see if anybody has an idea.
How do we do threshold onetime
signatures without coordination? This is
consensus people. What do we do?
>> Quorum intersection.
>> Yeah. Exactly. Exactly. So what we do is
the following. So we're going to uh
first of all we want no coordination. So
the assumption we're going to make is
that honest signers will never sign two
messages under a single public key.
However, dishonest signers might they
might sign, you know, might use their
signature shares to sign multiple public
keys, but we're going to put a bound on
the number of dishonest uh signers.
Okay. And then basically to make sure
that this the threshold scheme is
secure, we're going to require a core
intersection property. Namely, the
threshold needs to be greater than n
plus f f over two. And this should be
known to everybody in the blockchain
space. Right? If we have two corrupt
parties and the threshold is five and
say, you know, these three signers sign
one message and these three signers sign
another message. The point is the middle
guy will refuse to sign both M1 and M2
and the attacker simply cannot get uh
five shares on two different messages.
Okay, so that's kind of unusual that a
quorum intersection problem comes up in
the context of threshold signatures, but
that is necessary for one-time
signatures. So the next qu next question
to ask is what if we go beyond one-time
signatures? Suppose we have uh d time
signature. So you can sign up to d
messages. What is a generalization of uh
quorum intersection. This is maybe less
consensus like but let's walk through
the argument. So basically again we're
going to assume that honest parties will
only sign d messages under a single
public key. Okay each party will only
sign up to d messages. What that means
is that the adversary uh you know there
are n minus f h onest parties. So in
total the adversary can obtain D * N
minus F honest signature shares. Okay.
The adversary
has F secret keys. So in order to
generate a signature it needs N minus F
shares. Yes. Sorry. It needs T minus F
shares. T minus F shares because F keys
it already has. So that means that the
total number of signatures it can
generate is D * N minus F divided by T
minus F because it needs T minus F
shares per signature. So this is the
maximum number of signatures the
adversary can generate. Yeah, everybody
is okay with the logic. Cool. This is
the maximum number of signatures the
adversary can generate. And so for
example, if we have a threshold of n of
two n over three at most n over three
corrupt parties, uh that means the
adversary can get at most 2d signatures
per public key. Great. So this says that
uh if we if we want a d time threshold
signature with these parameters, what we
need to do is we need to start with a
few time signature scheme that's secure
for 2D signatures. Yeah, it's kind of
cool. Yeah. So 2D that's not too bad. So
we start with a few time signature
that's secure for 2D signatures and that
means that we can now generate a D time
threshold signature without any
coordination between the parties. Yeah,
that's kind of the argument. Um, it
turns out that for low threshold, so
here I'm kind of unhappy about this gap
between D and 2D, right? We get a D time
signature, but we really have to start
from a 2D secure scheme. So I'm a little
unhappy about the gap between D and 2D.
And I'll just tell you that if all you
want is like a two time signature or a
three time signatures, we can actually
close this gap by requiring a higher
threshold. Yeah, but for arbitrary
arbitrary thresholds we do we do need
these uh or rather for t= n over 3 2 n
over 3 we would we do need this gap
between um the number of times the
threshold signatures can be used versus
the number of times the underlying
signature can be used. Yeah. So far so
good. Okay. So now we understand what a
threshold uh one time or few time
signature so is. So now let's go to
constructions. So let's see how uh we
construct these things. So the main tool
we're going to use is something that we
call a contextaware threshold PRF. So
threshold PRFs have been around forever.
Context aware threshold PRF seems to be
something that comes up specifically for
building threshold hashbased signatures.
So let's start with threshold PRF. So
what is a threshold PRF? Well, it is
what you think it is. Yeah. So let's
just walk through uh the syntax. So we
have a pseudo random function that takes
a key and a value and produces a pseudo
random output. Yeah. It's a pseudo
random uh function. Uh so a threshold
PRF uh will the key generation algorithm
takes uh the number of users in a
threshold. It will generate a master
secret key for the PRF and then it will
generate n secret keys for the
participants in the threshold scheme.
There's an evaluation algorithm that
will take uh a secret key share in an
input and produce an a share of the uh
PRF evaluation. And then there's a
combine algorithm that will take the the
the coalition the quorum that's actually
uh generating the PRF value. We'll take
X and we'll take all the evaluation
shares and produce the actual
evaluation. Yeah. And the only property
we need is that in fact the evaluation
is the correct evaluation of the PRF
under the master secret key. And of
course if the adversary only has T minus
one evaluation shares, it learns nothing
about the value of the PRF at the point
X. Yeah, so far so good. That's a
threshold PRF. Okay, that's a standard
classic notion in cryptography. It has
many many many applications uh beyond uh
threshold hashbased signatures. So, but
for threshold hashbased signatures, it
turns out this is not enough. We need
something called a contextaware uh
threshold PRF. And here the idea is that
during evaluation, we add a context to
uh the evaluation algorithm. Yeah. So,
I'll explain what the context means in
just a second, but it basically affects
the security property of the threshold
PRF. So the point is the adversary
should learn nothing about the value of
the PRF unless it has T evaluation
shares for X all under the same context.
Yeah, if it's not under the same
context, it learns nothing. And so let
me explain this in a picture. So again,
three out of eight. Uh if you have three
people that collaborate together under a
single context, you can evaluate the PRF
at the point X. Yeah. So three people
under a single context can learn the
value of the PRF. However, if the
adversary let's say uh gets two shares
under one context, maybe two shares
under another context, two more shares
yet under another context, so it gets
six shares overall. These six shares
because they were generated under
different context will tell you nothing
about the value of the PRF at the point
X. Yeah, it's a stronger property of a
threshold PRF. And it turns out this is
what we need. Yeah, kind of a question
how to construct it, but this is what we
need. Yeah. Um, I'm sort of reminded
last year when I think you were talking
about encrypted meool.
>> Wow. Incredible. Wow. Tim, this is like
the best question you could have
possibly asked me.
>> I can't I can't believe you you
remembered, but this is amazing. Uh, so
last year I talked about encrypted
mempool where it turned out we needed
contextaware threshold encryption.
Threshold decryption rather. That's
exactly where the name comes from. But
this year we're not applying it to
threshold decryption. We're applying it
to threshold PRFs.
>> Is are the contexts the context back
then was like the block, right?
was the block height actually at the
hash of the block. Yeah, here the
context is going to be different,
>> but I can I can tell you what it what
it's going to be. The context is
actually going to be the message being
signed.
>> Yeah. So, if you're asking for
signatures on different messages from
different parties, you can't combine
those shares. That's the that's kind of
where we're headed.
>> Yeah, good good question. Amazing. You
can you remember this. Okay. So, yeah.
So, there's a formal definition of what
these things are. I just want to kind of
emphasize in the definition the point is
the adversary can obtain as many shares
as it wants for a particular X but they
would need to be under a different
context. Yeah. And that would reveal
nothing about the value of the PRF at X.
Okay. So the question is how to
construct these things. So I'll just
tell you we give two constructions in
the paper. Uh one is based on lises. We
use the BLMR lattice based PRF. Um, and
this actually gives us a contextaware
threshold PRF actually for very large N
and N&T. And so, you know, we're kind of
good to go and um uh and all all is
good. We also give a construction uh
kind of a combinatorial construction
just based on PRFs. Uh, but this one is
deficient in that it will only work when
n choose t is relatively small. Yeah.
So, you would ask, well, what's the
point of this? And again, the point of
uh the point of the Oh, by the way, the
reason it only works when N choose T is
small is because the secret keys tend to
be kind of big. Yeah, it's not in PRFs,
there's only a PRF value. There's
nothing to be big there, but the secret
keys actually tend to be uh big in that
environment. Uh the point is no matter
which one of these contextaware
threshold PRFs you use, the final
signature is a regular non- threshold
signature. Yeah, that's the point. Yeah,
which is again the philosophy of uh
threshold signatures, the threshold. So
whether I thresholdize my key or not is
nobody's business other than my own. So
the final signature should be a non-
threshold signature. Okay. So now that
we understand what context aware
threshold signatures are, the next thing
I want to do is show you the
construction. How do we use them to
build threshold hashbased signatures uh
and then if we have time maybe we will
look at some of that's how how these
threshold PRFs are actually built. Uh
okay. So to start off um I guess the
first thing we want to thresholdize is a
classic example of a one-time signature.
It's called the uh Winter's uh onetime
signature. So I'll tell you a bit of uh
historical trivia here. So Robert uh Bob
Winter's was actually a PhD student at
Stanford. Um and oddly even though this
is such a classic construction he never
published this. He never wrote this as a
paper. What happened there was
apparently Ralph Merkel gave a talk
about Merkel signatures and at the end
of the talk um uh Bob Winter goes up to
him and says well why did you just use
one hash value why couldn't you do more
hash values and basically that's where
winter's signatures come from and in
Merkel's thesis he attributes the idea
to win internets and that's why it's
called winter signatures um so my my uh
lesson from this for you guys is please
when you have interesting ideas write
them up write them up It's he was winter
was very lucky that Merkel uh
acknowledged him and that people
actually read Merkel's thesis to know to
call this idea winter signatures. I can
tell you this idea was developed over
the years many many many times over and
every every time the developer had to be
told well yeah this is already Merkel's
thesis it's called winter signatures.
Yeah. And the reason it was developed
over and over is because there was not a
paper on it. So yeah please write up
your your ideas. It's a good it's a good
lesson. Uh okay. So uh what are the
ingredients of uh these winter
signatures? So first of all, there's a
strange function that will take our
message and map it into some L long
vectors over the alphabet zero to W.
Okay? And I'll show you what uh how this
works in just a second. The property of
this function, this is kind of where the
signature gets its security from. The
property of this function is that it
needs to be cover free. What does cover
free mean? Cover free means that that
for every two messages it's not possible
that one message m0 is dominated by
another message. Yeah. So it all the
coordinates uh one message dominates the
other message. That's what it means to
be cover free and it also needs to be
collision resistant. The other
ingredient is a one-way function uh uh
called h. Actually it's not enough for
it to be a one-way function. So I'll
call this a hash function that operates
on the same domain and range. And
finally we have another compression
function that uh compresses x to the l
to some other small domain. Now for the
cryptographers in the room I'll say that
here I use collision resistance. Um it
turns out collision resistance is the
wrong thing to do in hashbased
signatures. But we can replace collision
resistance by what's called target
collision resistance. But for simplicity
here I'll just keep using collision
resistance. So before I can explain to
you how to thresholdize winter
signatures they're called watts. So
maybe I'll just say watts from now on.
Winter internet's onetime signatures.
Watts. So before I tell you how to
thresholdize watts, I have to explain to
you how watts works. Yeah, just to
remind you. Actually, I'm very curious.
How many of you know how watts works?
>> Oh, very few. Interesting. Okay, good.
Let's go. Let's go through it because
it's a beautiful construction.
>> Only the game theorist.
>> The cryptographers don't know how it
works. Oh, that's a little strange. But
uh Okay, let's go through it. It's a
very beautiful construction. So the way
winterets uh works is basically we start
off by generating a bunch of uh secret
values. Let's say x1 uh to x8. And what
we do is we build a hash chain out of
each one of these values. Okay, this is
the this was winter's idea. Don't just
do one step but go for a lot of steps.
And then we take all the top row of this
table. We hash it. Uh we shrink it down
to our short public key and that's our
public key. So now uh in practice I can
tell you like in SLH in SLHD GSA the
chains are about 16 long. In the shrunk
version of SLHD GSA the chains are about
four long for various reasons. How do we
sign? Uh the way we sign is basically
we're going to take our message and
apply the P function to it. And remember
the P function gives us a vector of
length 8. Yeah this vector basically
corresponds to various elements in this
chain. You can see two here means this
block, three here means this block, one
means this block and so on. So the the
the vector that the P function gives us
corresponds to kind of uh elements in
this block. I kind of like to think of
it as a cut that goes through the block.
So a signature really is kind of a cut
of the block and then the signature
itself is basically just the green the
green elements. Okay, that's it. Just
the green elements. How do you verify?
You take the elements in the signature,
you apply the hash the hash chain, you
get the top row, you hash the top row
and you compare it to the public key. So
that's a winter signature. Uh yeah. So
to verify, you just recmp compute the
public key and verify that it's that
it's the right one. Cool. Why is it
secure? Uh it turns out actually proving
security is a little tricky and actually
I could spend a whole hour just on the
story of security of winter. There's
probably a dozen papers on it. Uh but to
keep it simple, I'll just say that
security effectively comes from the
cover free property of P. Let make make
sure this is clear. Suppose we had one
message PM1
that dominated PM0. What does dominated
mean? It means that um everything in PM0
lies above things in PM1. That would
mean that given a signature on PM1, you
can actually derive a signature on on
M0, which we don't want. So the cover
free property means if I give you
another message, there must be some
block that the signature on M did not
reveal. And that basically is kind of
where uh security come from comes from.
So the cover free property is critical
for winter signatures. Okay. So now the
question is how do we thresholdize uh
winter signatures? And so let me show
you how this works. So the way we're
going to do it is well I think a pretty
natural uh approach. What we'll do is
we'll generate a threshold PRF. Okay. So
that will give us a master secret key
and a bunch of threshold PRF keys and
we'll give right signer number I is
going to is going to get secret key
number I. So everybody gets a very short
key uh for their work. The next thing
we're going to do is we're going to use
the PRF to generate uh the bottom row of
the winter table. And then the key
generator is just going to generate the
winter table just as before. All right,
but we're not done. We're not done. The
next thing the the key generator is
going to do is actually he's going to
take the um uh let's see. So the bottom
part just comes from the PRF. So we
don't need to do anything about that.
the top part of the winterest table,
we're going to take that and put it into
the combiner's public key.
Unfortunately, these elements are
secrets, right? If you can't just give
them to the combiner, the combiner is an
untrusted party. Yeah, it should not
have any secrets. So, we can't just give
these values to the combiner because
then it could forge signatures on our
behalf. So, what we're going to do is
we're going to take each and every
element in this table and we're going to
encrypt it. Onetime pad encrypt it using
the PRF. Okay. Okay, so this gives us an
encrypted winter table that we give to
the combiner. So you know in practice uh
the size of this table is not very big.
So we can just you know give this key.
It's not uh for at least for winter
signatures it's not that big and the
combiner will store it. Okay. Now it
should be kind of clear to you how we
sign. So remember a signature
corresponds to a cut uh through the
table. And basically what every party
will do when it signs a message is it
would release a PRF evaluation share for
each one of these blocks. Yeah. So
basically we will reveal all this says
is we reveal an evaluation share for
each one of these blocks when we sign
the message M. Now if the combiner gets
enough shares from the signers, it can
reconstruct the PRF value and then
unblind the value in the combiner's
public key, recover the corresponding
element in the winter table and get the
signature as a result.
>> Yeah.
>> So that's your context each one of
these.
>> No, no, no, no. So we didn't say context
yet. The context actually when we do the
evaluation shares for each one of these,
uh, we're going to have to use the
message as the context. And you'll see
why that's important uh in just a
second. Yeah. But I want to make first
of all sure it's clear how signing
actually works. Yeah. So every signer uh
what they do is they basically reveal in
this case eight evaluation shares. One
share for every element in the winter
table. Yeah. And if the combiner gets
eight evaluation shares from t different
signers, it can evaluate the PRF at
those eight points and then unmask the
value from the combiner public key and
that becomes the signature. So that's
how we do threshold signing. Now why is
the evaluation context so important?
Yeah, let me just give you an example to
illustrate why it's so important. Well,
imagine we have um one message just
dominated by two different messages.
Yeah. So in a one-time signature, this
can't have one one message cannot be
dominated by one message, but it could
be dominated by two different messages.
Yeah. This means if you have a signature
on M1 and a signature on M2, you can
forge a signature on M. Okay. So now
what's the what's the problem? Let's
imagine let's go back to the lampport
world where where the depth of the
signature is the depth of the change is
only one. So what's the problem? So
imagine the adversary asks T over two
parties to release shares on these three
at these three points. Yeah. P of M
happens to be these three points. So the
combi the the adversary will only get T
over two shares. That doesn't help them
do anything. Yeah. But now we can ask
for t over two shares from for another
message and t over2 shares for another
message. And now you see the problem for
each one of these uh red red uh squares
here. Now the the adversary has t shares
even though it didn't get t-shares for
any single message. So in principle
given all these shares the adversary
should get nothing no signature at all.
But here because it has T-shares for
each one of um the values needed for P
ofm it would get a signature of P ofM.
Yeah. And so the context using the
message as the context basically makes
sure that we can't combine shares from
different uh signatures from signing
different messages and as a result uh
the adversary will get nothing. Yeah. So
without the context this would strictly
be insecure. The context is what makes
this work. Yeah. Make sense? Okay. Cool.
So yeah this this is basically what this
is. All right. So uh so given this
threshold winter and the the context we
can now prove a security theorem. So the
theorem says that this watts threshold
signature is in fact adaptively secure.
If we have a contextaw aware threshold
PRF that's adaptively secure. The
function piece collision resistant. The
hash function is we have this property
called pre-image resistant on iterates.
So it's an interesting story in its own
right but that's what we need to analyze
winter. Um and then the the the the uh
final compression function is target
collision resistance. Okay. So um uh yes
so that's a security theorem. One
technical point I want to make which I
think is also interesting is here we had
to make sure that our function P is
collision resistant. Yeah. And I told
you that uh generally we want to avoid
collision resistance. We want to use
target collision resistance. And just
for a technical reason, it turns out if
we want to replace this collision
resistance with target collision
resistance, it turns out in the signing
procedure, we need to have a second
round. Yeah. So signing becomes a two-
round process because the signers need
to generate some randomness for the TCR
function. So it's kind of an interesting
interesting point. Um that even for
winter, it turns out we need a two-
round signing protocol in reality. Uh
fine. So now we have a threshold winter
scheme. And the maybe the last thing
I'll say, oh, I have to stop. So I'll
maybe just go through this slide and
I'll stop is what about other signature
schemes. So we can apply this to you
know the few time signatures XMSS and
fours it works just just fine. Uh if you
have a D time stateful signature the key
generator time would have to work D
times as hard because it needs to
generate D winter's public keys. Yeah.
So the combiner public key and the key
generator basically everything blows up
by a factor of D. And because of it of
this this doesn't apply to SLSGSA. So in
SLHSA remember we have a tree with 2 to
the 64 signatures 2 to the 64 leaves
that the combiner public key would just
become too big. So this doesn't apply uh
to SLHDsa. It's kind of important to
understand. But at least what we can do
is if we if you uh really want to
thresholdize uh SLHDSA,
we can do it using MPC and our
techniques basically would greatly
simplify the MPC process because you
have to actually um apply run shot 5
shot 256 under MPC far fewer times using
our method. Yeah. So at least it doesn't
avoid the MPC altogether, but it does
simplify it uh simplify it quite a bit.
So kind of that's uh that's where we
are. So I guess in the negative two
minutes that I have, I was going to tell
you about how to build these
contextaware threshold PRFs, but maybe
we'll do that uh we'll do that offline.
I'll skip that. I'll just tell you we do
have a context, we do have these two
constructions. Uh but maybe we'll do
that some other time. Okay. Okay, so
just to summarize uh hashbased
signatures uh basically we we build
threshold hashbased signatures for large
uh N&T. The blockchain again remembers
obtains a regular signature just as we
know and love. Um uh and basically the
signers all they do is they just use
this contextaware uh threshold PRF.
Unfortunately the scheme is quite
difficult to uh build a distributed key
generator for. So one of the things
we're working on now is how do we also
get a DKG for these hashbased
signatures. Uh, and of course, uh,
silent setup means that we'd like to be
able to change N&T on the fly. So, it's
kind of interesting, uh, to take our
threshold PRFs and make them, uh,
silent, uh, which is kind of a a cool
project on its own right. So, these are
kind of things that we're working on,
uh, now. All right. So, I guess I'll
stop here and I'll say the paper is
frankly frantically being worked on and
hopefully it'll be out out in a in a
week or two.
>> Yeah. Um so if I understand correctly u
latisbased uh construction give you a
bit of an algebra that you can play
with.
>> Exactly.
>> While hushbase don't and so what you do
is whenever you need to play a little
bit with the algebra when you use your
latis and then you you englobe inside
your hashbase. Can you farm that trick
to get blind signatures string
signatures and something else like that?
>> Oh my god that is such a great question.
Um, so like could we do blind signatures
on hashbased signatures using a using a
lattice based scheme somehow?
>> Let's see. The signature itself would be
hashbased, but the protocol would be
would be lattis based.
>> Yeah.
>> Um, I don't know. I think that's a
fantastic question.
>> Yeah, I would suspect the answer is yes,
but that's a wonderful thing to do.
>> Absolutely. Great, great question.
>> Do you also have robustness in your
threshold? PRF robustness like what if
someone lies about the PRF shell that
they give you.
>> Yeah. Yeah. Yeah. So rob I mean you add
robustness in the usual way. So this is
a lattice based PRF so you would just do
uh you know you just add a proof of
knowledge for for robustness. Yeah it's
it's a good point but that but that kind
of uh because it's a lattice based PRF
we can we can just make it robust in the
usual ways.
>> Yeah it's a good it's a good point.
>> Great. Yeah please.
>> I'm curious what you're hearing about
just the how people plan to deal with
the bigger signature size. It seems
likely to come out of these hashbased
schemes. So like Bitcoin, like do they
want to increase the block size? Do they
want to increase the witness discount or
>> Yeah. Yeah. So So Ethereum's answer is
basically we're going to take all the
signatures, these large signatures in a
block and we're going to snarkify them.
Yeah, that's their their solution. So
every 12 seconds they'll have to
generate a um a snark that says all the
signatures in a block are correct. Uh
Bitcoin basically it's unknown right now
to be honest. So they are um right now
they are working out the details of the
signature scheme. So it's called
shrinks. Uh so the BIP for shrinks is
like being written like this summer. Um
and yes it is even though the actual
signatures that are going to be used are
stateful signatures. So you know they're
not as terrible as the stateless one
they're still hundreds of bytes whereas
today 64 bytes.
>> So the signature cost is going to go up
by a factor of 10. Um and how they're
going to deal with it you know it's it's
um right now they're kind of ignoring
this problem. There's some within the
core devs, some of them are saying, "Oh,
we're going to have to go back to the,
you know, block size wars and increase
the block size." But at least we're not
increasing the number of number of
transactions. We're just increasing the
block size because of these signatures.
Um, but how they actually deal with it
is is is currently unknown.
>> Yeah. So, that that's where we are.
>> Yeah. Yeah. It's a good uh it's a good
question actually. Even um I I have to
say the Bitcoin making Bitcoin
postquantum that is uh a really
interesting discussion overall. Yeah,
that I could have just did my did my
whole talk just on that. Um how to
transition tap routt to be postquantum
for example. There's lots of different
proposals. There's actually right now
there's very active debate between the
different proposals. Of course I have my
own opinions that I'd be happy to share.
Uh maybe some other time though. Um uh
so yeah, it's a pretty pretty
interesting uh area in its own right.
just this question and by the way this
is even ignoring the elephant in the
room which you know the elephant in the
room is what to do about abandoned
abandoned assets or more generally
abandoned assets that is an extremely
complicated question yeah I when I
started thinking about this I thought oh
it's kind of obvious what to do but that
is going to be a very difficult uh issue
to the point where we want to delay that
as much as we can and the actually I can
tell you one of the proposals now um is
the way we deal with abandoned assets
assets is basically we set up an address
on Bitcoin let's say the digits of Pi
that will just sit on the Bitcoin
network and as long as no one has broken
that address people will just keep on
using keep on making those assets
keeping them alive the minute that uh
address is broken that will trigger the
miners to cancel ECDSA yeah this of
course is based on the assumption that
the first person to build a quantum
computer is a good
Right. Uh but most likely it's going to
be one of the good guys. Most likely.
Yeah. Um one can hope. Yeah. Uh one can
hope. And so um so they the good guys
will then break this one address and
that will automatically trigger a
cancelling of ECDSA so that the
abandoned assets would have to go
through a separate recovery procedure.
And there's a whole community of people
now working on what is the correct
recovery procedure once ECDSA is is
canceled. It's not that you revoke the
abandoned assets. You kind of
automatically revoke them, but then they
would be they would go through a
recovery procedure. And how that
recovery procedure works is kind of a
very very interesting uh problem in its
own.
>> So there's even technical questions to
be solved, not just political question.
>> I mean, they're not Yeah, there are.
They're not terribly difficult. Okay,
since you asked, give me one more minute
and I'll say I'll say one interesting
idea. So how does Satoshi protect
himself? Right. Okay. So, Satoshi um uh
how does like after ECDSA is revoked,
let's say Satoshi is reanimated 100
years from now and he wants to claim his
his assets by then ECDSA has been
revoked, he has no way he or she or
whatever they uh they have no way of
proving that they are Satoshi. Yeah.
Right. Because a quantum computer
exists, anybody can generate the secret
keys. So, how does he uh how does how do
they actually prove that it's their
assets? Well, one cute idea is today
they can get a they can make a
transaction that spends the Satoshi
coins. The problem is they they can't
just post this transaction on chain
because that would reveal that Satoshi's
alive. Yeah. That they somebody knows
the key. So what they'll do is they'll
create a commitment a hiding commitment
to that transaction. Use an operator
return to push that commitment on chain.
And now 100 years from now they can go
back and say look in 2026 when there
were no quantum computers I created this
transaction that shows that I knew the
secret key back in 2026 therefore you
should give me my tokens. So even though
the assets are revoked there there's a
path by which you have recovery. Yeah.
So people are kind of talking about
recovery paths along those lines. Um and
so again there's a lot a lot of details
to work out here and yeah so hopeo
hopefully but this is like I said this
is such a difficult topic that that's
going to be pushed away pushed um uh to
later right now the question is how do
we protect Bitcoin holders who are
active and can actually move their
assets once a mechanism is available.
Cool. Thanks a lot.
>> Thanks again.
--- TRANSCRIPT END ---
