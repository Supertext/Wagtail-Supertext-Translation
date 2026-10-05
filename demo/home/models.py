from wagtail import blocks
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page

BODY_BLOCKS = [
    ("heading", blocks.CharBlock(form_classname="title", label="Heading")),
    ("paragraph", blocks.RichTextBlock(features=["bold", "italic", "link", "ol", "ul"], label="Paragraph")),
    ("quote", blocks.StructBlock([("text", blocks.TextBlock()), ("author", blocks.CharBlock(required=False))], label="Quote")),
]


class HomePage(Page):
    intro = RichTextField(blank=True, features=["bold", "italic", "link"])
    body = StreamField(BODY_BLOCKS, blank=True)

    content_panels = Page.content_panels + ["intro", "body"]
    subpage_types = ["home.ArticlePage"]


class ArticlePage(Page):
    intro = RichTextField(blank=True, features=["bold", "italic", "link"])
    body = StreamField(BODY_BLOCKS, blank=True)

    content_panels = Page.content_panels + ["intro", "body"]
    parent_page_types = ["home.HomePage"]
