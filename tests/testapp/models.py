from wagtail import blocks
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page


class ArticlePage(Page):
    intro = RichTextField(blank=True)
    body = StreamField([("heading", blocks.CharBlock()), ("paragraph", blocks.RichTextBlock())], blank=True)

    content_panels = Page.content_panels + ["intro", "body"]
