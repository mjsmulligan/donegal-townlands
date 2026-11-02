Griffith's Valuation – Source Acquisition and ETL Specification

Status: Proposed – technical discovery required
Source: Ask About Ireland, Griffith's Valuation
Geographical scope: County Donegal
Work package: WP14 – Property and land model

1. Purpose

Acquire and preserve Griffith's Valuation source material for Donegal Townlands, and provide a traceable basis for extracting structured information about properties, holdings, occupiers and valuations.

The acquisition process and the subsequent interpretation of the records are separate activities.

2. Source acquisition

Investigate automated acquisition using Python ("requests", "BeautifulSoup" or equivalent).

The preferred approach is to interact directly with the archive's search and document endpoints rather than automate browser interaction.

Initial technical discovery must establish:

- Search endpoint and accepted parameters.
- How parishes and valuation records are enumerated.
- Pagination and session requirements.
- Stable record identifiers.
- How original valuation page images are delivered.
- Whether full-resolution images are available.
- How associated valuation maps are delivered.

XML endpoints, including "index.xml" and "details.xml", are candidates for investigation.

No assumptions about endpoint structure or image availability should be treated as established until tested.

3. Acquisition priorities

Treat two resource types separately.

A. Original valuation pages – first priority

Acquire the original scanned valuation book pages. These contain the documentary evidence for occupiers, immediate lessors, property descriptions, acreage and valuations.

B. Valuation maps – second priority

Investigate map acquisition separately. Maps may be delivered as complete images, image tiles or through an interactive mapping service.

Preserve map identifiers and their relationship to valuation records wherever available.

4. Preservation and provenance

Original downloaded images must be retained unchanged.

For each acquired image, maintain a manifest containing:

- Source repository.
- Original record identifier.
- Original source URL and retrieval parameters.
- Retrieval timestamp.
- Local filename and storage location.
- Content type and image dimensions.
- File checksum.
- Acquisition outcome and any errors.

Use the original source identifier as the primary locator wherever it is stable.

Do not download duplicate copies of the same source image merely because it appears in multiple search results.

5. Processing and extraction

Keep acquisition independent of transcription and interpretation.

The initial ETL should establish the source inventory and its relationship to Donegal places. It should not attempt to infer people, families or property identities automatically.

Subsequent extraction should preserve:

- Original transcribed values.
- Normalised values, where required.
- Uncertain or illegible readings.
- References to the original image and page.
- Links between observations and the relevant place.

The property and land model is developed separately from the genealogical model. Links to established people must be supported by evidence and human review.

6. Acquisition scope

Use the Donegal place register as the basis for discovery, initially by civil parish.

However, acquisition must not be restricted to townlands currently under investigation. Preserve the complete relevant source results and make place selection and association decisions during processing.

7. Technical requirements

The acquisition script should:

- Use a persistent HTTP session where required.
- Set appropriate request headers and timeouts.
- Handle failed requests and retry appropriately.
- Respect server rate limits and access conditions.
- Validate downloaded content before accepting it as an image.
- Detect duplicates using stable source identifiers and checksums.
- Support resumption without downloading existing material again.
- Log errors and incomplete acquisitions.
- Be repeatable and safe to run again.

Bulk acquisition must comply with the archive's applicable access and reuse conditions.

8. Initial discovery milestone

Before building the full downloader, implement a small Python probe against one known Donegal townland.

Demonstrate:

1. A successful place search.
2. Enumeration of matching valuation records.
3. Extraction of stable record identifiers.
4. Retrieval of an original valuation page image.
5. Validation of the image and its resolution.
6. Recording of source metadata in a manifest.
7. Identification of the associated map resource, if available.

9. Acceptance criteria

The discovery milestone is complete when:

- A known townland can be searched programmatically.
- All matching records returned by the test search can be enumerated.
- At least one original valuation page can be downloaded and validated.
- Its source identifier and URL are preserved.
- The acquisition manifest is generated.
- A second run does not create duplicate downloads.
- The original image can be traced from a prospective observation back to the source.

Map acquisition is not a dependency for completing this initial milestone.

10. Open decisions

- Exact archive endpoint and request protocol.
- Availability and resolution of original images.
- Map image and tile delivery mechanism.
- Final source directory and manifest format.
- Property, holding and valuation observation schemas.
- Transcription strategy: manual, assisted or automated.
- Archive reuse and bulk-download conditions.

Design principle: Preserve the documentary source first. Extract and interpret its contents separately. Every derived observation must remain traceable to the original evidence.