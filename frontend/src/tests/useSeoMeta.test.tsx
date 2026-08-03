import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useSeoMeta } from "../seo/useSeoMeta";

function Harness(props: Parameters<typeof useSeoMeta>[0]) {
  useSeoMeta(props);
  return null;
}

describe("useSeoMeta", () => {
  it("sets the document title and description", () => {
    render(<Harness title="Lemon Tart — Cookbook" description="A tangy dessert." />);

    expect(document.title).toBe("Lemon Tart — Cookbook");
    expect(document.head.querySelector('meta[name="description"]')).toHaveAttribute(
      "content",
      "A tangy dessert."
    );
  });

  it("defaults to index,follow and switches to noindex,nofollow when requested", () => {
    const { rerender } = render(<Harness title="Public page" />);
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute(
      "content",
      "index,follow"
    );

    rerender(<Harness title="Private page" noindex />);
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute(
      "content",
      "noindex,nofollow"
    );
  });

  it("sets Open Graph tags", () => {
    render(
      <Harness title="Lemon Tart" description="Tangy." image="https://example.com/tart.jpg" />
    );

    expect(document.head.querySelector('meta[property="og:title"]')).toHaveAttribute(
      "content",
      "Lemon Tart"
    );
    expect(document.head.querySelector('meta[property="og:description"]')).toHaveAttribute(
      "content",
      "Tangy."
    );
    expect(document.head.querySelector('meta[property="og:image"]')).toHaveAttribute(
      "content",
      "https://example.com/tart.jpg"
    );
  });

  it("sets a canonical link and removes it once omitted", () => {
    const { rerender } = render(<Harness title="A" canonical="https://example.com/a" />);
    expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute(
      "href",
      "https://example.com/a"
    );

    rerender(<Harness title="A" />);
    expect(document.head.querySelector('link[rel="canonical"]')).toBeNull();
  });
});
