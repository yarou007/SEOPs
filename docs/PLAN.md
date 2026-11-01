# SEOPs plan

Client-facing platform where each client connects their own analytics sources (Search Console, GA4, Ahrefs, and later others) and sees all of them on one dashboard.

Status key: [ ] not started, [~] in progress, [x] done

## Core analysis

The ordered product questions, source gaps and next actions are recorded in
[Analysis axes](ANALYSIS_AXES.md).

## Assumptions
- You create client organizations and invite their users. Self sign-up comes later.
- Google access uses service accounts. Clients add our service-account email to their own properties. OAuth comes later, if ever.
- Ahrefs data comes from CSV exports. No Ahrefs API.

## Step 1: Real Google data for one site
- [ ] Grant the service account access to `dcemergencylockanddoor.com` in Search Console and GA4
- [ ] `check_gsc.py` prints real numbers
- [ ] Real GSC and GA4 sync for that site
- **Done when:** sync numbers match the Google UIs over the same window

## Step 2: Organizations
- [ ] `organizations` table, memberships (owner, member, viewer)
- [ ] Sites belong to an organization
- [ ] Access checks: user must be a member of the site's organization
- **Done when:** a user in organization A gets 404 on organization B's sites, tested end to end

## Step 3: Connector pattern
Each platform implements the same four parts:
1. Setup steps (client-facing text)
2. Live connection check
3. Sync that loads history
4. Data for the dashboard
- [ ] GSC and GA4 rebuilt as the first two connectors
- **Done when:** adding a platform means writing one connector, with no changes elsewhere

## Step 4: Onboarding wizard
Pick platforms → setup steps per platform → live check → first sync with progress → dashboard. Replaces the current add-website form.
- **Done when:** a tester who has never seen the app connects GSC and GA4 using only on-screen instructions

## Step 5: Ahrefs CSV connector
- [ ] Sample export received
- [ ] Upload parser and Ahrefs tab
- **Done when:** upload appears on the Ahrefs tab, and re-uploading the same date replaces the data

## Step 6: Hardening
- [ ] Server-side sessions (logout ends access immediately)
- [ ] Invite flow with single-use links
- [ ] Basic privacy notice for client data
- **Done when:** a revoked session is rejected at once, and an invite link works once

## Step 7: Pilot with one client
- [ ] A real client connects their own platforms through the wizard
- **Done when:** the client sees their history with no open questions about setup

## Step 8: More platforms
One connector at a time, after the pilot. Platforms to be confirmed.

## Parallel work
Steps 2 and 3 are code work that doesn't need Google access, so they can run while Step 1 waits on access.

## Open decisions
- Which platforms beyond GSC, GA4, and Ahrefs
- Hosting: Hetzner or n8n Cloud (CEO)
- Whether clients self sign-up later or are always invited