"""Sample intake emails for Phase 1 tests."""

CLEAR_QUALIFIED = """Subject: Car Accident - Need Legal Help

Dear Attorney,

My name is Sarah Johnson and I was involved in a car accident on February 15, 2026
at the intersection of Main St and Broadway in Springfield. The other driver, James
Miller, ran a red light and T-boned my vehicle. I was taken to Springfield General
Hospital where I was treated for a broken collarbone and whiplash.

I've been unable to work for the past 6 weeks. My medical bills are currently at
$45,000 and climbing. My car was totaled — it was a 2022 Honda Civic worth about $28,000.

I found your firm through a Google search. My phone number is (555) 123-4567 and
my email is sarah.johnson@email.com.

I'd like to schedule a consultation as soon as possible.

Thank you,
Sarah Johnson
"""

CLEAR_UNQUALIFIED = """Subject: Question about my parking ticket

Hi, I got a parking ticket last week for $75 and I think it's unfair because the
sign was blocked by a tree. Can you help me fight it? My name is Tom Davis, email
tom.davis@email.com.
"""

AMBIGUOUS = """Subject: Legal matter

Hello, I have a situation at work that I think might be illegal. I don't want to
get into details over email but it involves my boss and some questionable practices.
Can someone call me? Thanks. - Mike
"""

POTENTIAL_CONFLICT = """Subject: Breach of Contract — Anderson Manufacturing

Dear Counsel,

I'm reaching out regarding a breach of contract dispute with Anderson Manufacturing
LLC. I am the CEO of Pacific Supply Co. Anderson has failed to deliver $2.3 million
worth of industrial equipment per our agreement dated June 2025. We've attempted to
resolve this directly but they are now refusing to communicate.

Contact: Robert Chen, robert@pacificsupply.com, (555) 987-6543

We need to move quickly as the contract has a 12-month dispute resolution clause
that expires in August 2026.

Robert Chen
CEO, Pacific Supply Co.
"""

URGENT = """Subject: URGENT — Statute of Limitations Expiring

I was injured at my workplace 2 years and 11 months ago. I just learned that the
statute of limitations for personal injury in our state is 3 years. That means I
only have about 30 days to file. Please contact me IMMEDIATELY.

Maria Garcia, (555) 222-3333, maria.garcia@email.com
Injury: Chemical burn at Westfield Chemical plant on May 14, 2023
"""
