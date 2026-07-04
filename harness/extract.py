from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from playwright.sync_api import ElementHandle, Page

INTERACTIVE_SELECTOR = (
    "button, "
    "a[href], "
    "input:not([type='hidden']), "
    "select, "
    "textarea, "
    "[role='button'], "
    "[role='checkbox'], "
    "[role='link'], "
    "[role='menuitem'], "
    "[role='radio'], "
    "[tabindex]:not([tabindex='-1'])"
)


@dataclass(frozen=True)
class ElementInfo:
    index: int
    id: str
    role: str
    text: str
    checked: bool | None
    visible: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "id": self.id,
            "role": self.role,
            "text": self.text,
            "checked": self.checked,
            "visible": self.visible,
        }


def extract_elements(page: Page) -> tuple[list[dict[str, Any]], dict[int, ElementHandle]]:
    elements: list[dict[str, Any]] = []
    handles: dict[int, ElementHandle] = {}
    seen_ids: set[str] = set()

    for handle in page.query_selector_all(INTERACTIVE_SELECTOR):
        if not handle.is_visible():
            continue

        element_id = (handle.get_attribute("id") or "").strip()
        if not element_id:
            continue
        if element_id in seen_ids:
            raise ValueError(f"Duplicate interactive element id found: {element_id}")
        seen_ids.add(element_id)

        index = len(elements)
        info = ElementInfo(
            index=index,
            id=element_id,
            role=_role(handle),
            text=_text(handle),
            checked=_checked(handle),
            visible=True,
        )
        elements.append(info.to_dict())
        handles[index] = handle

    return elements, handles


def _role(handle: ElementHandle) -> str:
    explicit = handle.get_attribute("role")
    if explicit:
        return explicit

    tag = (handle.evaluate("element => element.tagName.toLowerCase()") or "").lower()
    input_type = (handle.get_attribute("type") or "").lower()
    if tag == "input":
        return input_type or "textbox"
    if tag == "a":
        return "link"
    return tag


def _text(handle: ElementHandle) -> str:
    aria = handle.get_attribute("aria-label")
    if aria:
        return " ".join(aria.split())

    tag = (handle.evaluate("element => element.tagName.toLowerCase()") or "").lower()
    if tag in {"input", "textarea", "select"}:
        label = handle.evaluate(
            """element => {
                if (element.labels && element.labels.length) {
                    return Array.from(element.labels).map(label => label.innerText).join(" ");
                }
                return element.getAttribute("placeholder") || element.getAttribute("value") || "";
            }"""
        )
        return " ".join(str(label or "").split())

    text = handle.inner_text()
    return " ".join(text.split())


def _checked(handle: ElementHandle) -> bool | None:
    role = (handle.get_attribute("role") or "").lower()
    input_type = (handle.get_attribute("type") or "").lower()
    if role in {"checkbox", "radio"} or input_type in {"checkbox", "radio"}:
        return handle.is_checked()
    aria_checked = handle.get_attribute("aria-checked")
    if aria_checked is not None:
        return aria_checked.lower() == "true"
    return None
