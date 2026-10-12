# SystemEarth updates received 13 October 2026

Source: user-supplied teammate and project-runner messages dated 12 October, plus the attached screenshot. Wording below is preserved from the user's transcription. Attachments are saved in this repository for local work; public redistribution permission for the company sample has not been established. No external publication is authorized by this checkpoint.

## Teammate messages

> Yeah I tht we needed something

Mrigakshi, 12 October 2026, 3:59:19 PM:

> SystemEarth said at the kickoff that the dataset and use case are open and teams won’t be penalised for which datasets they choose. The layers they described are all free and public, so you can start today.
> Download these now:
> Forest at the 2020 cut-off: JRC Global Forest Cover 2020. It’s on the EU Forest Observatory site and in Google Earth Engine.
> Forest loss by year: Hansen / UMD Global Forest Change. Download it from the GLAD (University of Maryland) site. For Songkhla you only need one tile, labelled 10N_100E, which covers 0–10°N and 100–110°E. Get the lossyear and treecover2000 files.
> Protected areas: WDPA from protectedplanet.net. Filter it to Thailand.
> Farm plots: generate synthetic plot polygons in Songkhla, a few hundred to a few thousand, at realistic rubber smallholding sizes. Deliberately include edge cases: plots on forest edges, very small plots, and plots overlapping protected areas. This is actually better than real data for testing.

Additional teammate clarification:

> I just said rubber use case simply, we can discuss abt that later amongst ourselves

These are teammate suggestions, not verified data access or a final team selection. Rubber and Songkhla remain provisional. Synthetic edge cases complement real samples; they do not establish real-world accuracy.

## Project-runner messages

Matthew Saw, 12 October 2026:

> [6:29:40 PM] hey peeps, in case yall need something to start, here is a sample of the data we collect from our customers
> [6:30:41 PM] it contains a geojson file, which is the file we use to do the overlap analysis, and a due dilligence report. It's a giant CSV basically with all the due diligence data. Most of it is actually checking whether suppliers have performed their due diligence against the farms they work with
> [6:31:12 PM] we collect geojsons, do some analysis, then we check against the submitted due diligence to see whether our analysis results measure up against theirs
> [6:31:26 PM] hope this helps!
> [6:33:03 PM] here are some datasets we use
> https://glad.umd.edu/dataset
> and here is a killer resource for any kind of dataset you might want https://globalnaturewatch.org/map

Attachments saved unchanged in `data/company-sample/2026-10-12/`:

- `200001-17plots-valid_2025-08-02T09_11_12Z.csv`
- `200001-17plots-valid.geojson`

## Screenshot transcription

Image: [organizer reply](organizer-reply.jpg), supplied as `IMAGE 2026-10-13 00:06:46.jpg`. The screenshot says “Today”; its exact conversation date is not independently established.

> [4:03 PM] Hi! For the SystemEarth geospatial challenge, will you be sharing any datasets or sample plot boundaries? In the meantime, we’re building with public layers (JRC GFC2020, Hansen Global Forest Change, WDPA) for a rubber use case in Songkhla, Thailand. Hope that’s okay!
>
> [4:04 PM] Hey!! Yes this should be great!
>
> [4:04 PM] I’ve already bumped the companies and they’ve acknowledged it
>
> [4:05 PM] Still waiting on them to provide any extra information in the group chats

This supports using public layers while waiting; it does not settle final team scope, detailed screening rules, or dataset reuse terms.

## Current user direction

- Save the supplied materials locally and commit before further investigation.
- Review recent Claude/Codex repository threads and continue planning.
- Delegate the heavy investigation and artifact work; the main agent manages, reasons, reviews, and integrates.
- Download useful additional data as needed.
- Develop compelling product and UI/UX ideas; Claude will do the design.
- Create and invoke a reusable skill that evaluates the proposal from a hackathon judge's perspective.
