import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ImageSlider } from "../frontoffice/ImageSlider";
import { LanguageProvider } from "../i18n/LanguageContext";

function renderSlider(images: string[]) {
  return render(
    <LanguageProvider>
      <ImageSlider images={images} alt="Lemon Tart" />
    </LanguageProvider>
  );
}

describe("ImageSlider", () => {
  it("renders nothing when there are no images", () => {
    const { container } = renderSlider([]);

    expect(container.firstChild).toBeNull();
  });

  it("shows a single image with no controls or counter", () => {
    renderSlider(["/images/a.jpg"]);

    expect(screen.getByAltText("Lemon Tart")).toHaveAttribute(
      "src",
      "http://localhost:8000/images/a.jpg"
    );
    expect(screen.queryByRole("button", { name: "Previous photo" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next photo" })).not.toBeInTheDocument();
    expect(screen.queryByText("1 of 1")).not.toBeInTheDocument();
  });

  it("navigates forward and backward through multiple images, wrapping at both ends", async () => {
    const user = userEvent.setup();
    renderSlider(["/images/a.jpg", "/images/b.jpg", "/images/c.jpg"]);

    expect(screen.getByAltText("Lemon Tart")).toHaveAttribute(
      "src",
      "http://localhost:8000/images/a.jpg"
    );
    expect(screen.getByText("1 of 3")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next photo" }));
    expect(screen.getByAltText("Lemon Tart")).toHaveAttribute(
      "src",
      "http://localhost:8000/images/b.jpg"
    );
    expect(screen.getByText("2 of 3")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Previous photo" }));
    expect(screen.getByAltText("Lemon Tart")).toHaveAttribute(
      "src",
      "http://localhost:8000/images/a.jpg"
    );

    await user.click(screen.getByRole("button", { name: "Previous photo" }));
    expect(screen.getByAltText("Lemon Tart")).toHaveAttribute(
      "src",
      "http://localhost:8000/images/c.jpg"
    );
    expect(screen.getByText("3 of 3")).toBeInTheDocument();
  });

  it("navigates with the left/right arrow keys once the slider is focused", async () => {
    const user = userEvent.setup();
    renderSlider(["/images/a.jpg", "/images/b.jpg"]);

    screen.getByRole("group").focus();
    await user.keyboard("{ArrowRight}");

    expect(screen.getByAltText("Lemon Tart")).toHaveAttribute(
      "src",
      "http://localhost:8000/images/b.jpg"
    );

    await user.keyboard("{ArrowLeft}");
    expect(screen.getByAltText("Lemon Tart")).toHaveAttribute(
      "src",
      "http://localhost:8000/images/a.jpg"
    );
  });
});
