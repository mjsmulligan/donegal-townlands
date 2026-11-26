"""Credit text for images that carry a licence condition (docs/MEDIA_SPEC.md, scope `census`).

A media.csv row names one of these keys in its `credit` column. The story page lists, under "Credits and
licences", the credit of every key its images use, and a one line short credit sits under each image.
The wording is the custodian's own. Where the custodian gives exact words, they are kept as given and
never reworded. Standard library only.

Keys:
    nai1926   National Archives of Ireland, 1926 Census images (CC BY 4.0). Wording given by the user
              from the NAI reuse page, 2026-11-26.
"""

CREDITS = {
    'nai1926': {
        'short': 'National Archives of Ireland, 1926 Census, CC BY 4.0',
        'text': ('This work includes content from records of the 1926 Census of Ireland, made available by the '
                 'National Archives of Ireland under the Creative Commons Attribution 4.0 International (CC BY 4.0) '
                 'licence. Please see further'),
        'link_word': 'here',
        'link': 'https://nationalarchives.ie/search-the-1926-census-2/permission-to-reuse-census-1926/',
        # CC BY 4.0 asks that changes are indicated. The images are converted and resized, never cropped.
        'modified': 'Images converted and resized for display.',
    },
}


def credit_block(key):
    """The page data for one credit key: {short, text, link_word, link, modified}. KeyError if unknown."""
    return dict(CREDITS[key])
