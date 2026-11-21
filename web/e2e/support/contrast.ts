import type { Locator } from "@playwright/test";

/** Render CSS Color 4 values to sRGB and composite actual ancestor surfaces. */
export async function textContrast(locator: Locator) {
  return locator.evaluate(async (element) => {
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
    await Promise.allSettled(
      element.getAnimations().map((animation) => animation.finished),
    );
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const context = canvas.getContext("2d")!;
    function rgba(color: string) {
      context.clearRect(0, 0, 1, 1);
      context.fillStyle = color;
      context.fillRect(0, 0, 1, 1);
      return [...context.getImageData(0, 0, 1, 1).data];
    }
    function over(top: number[], bottom: number[]) {
      const alpha = top[3] / 255;
      return top
        .slice(0, 3)
        .map((channel, i) => alpha * channel + (1 - alpha) * bottom[i]);
    }
    const chain: Element[] = [];
    let current: Element | null = element;
    while (current) {
      chain.unshift(current);
      current = current.parentElement;
    }
    let background = [255, 255, 255];
    for (const ancestor of chain)
      background = over(
        rgba(getComputedStyle(ancestor).backgroundColor),
        background,
      );
    const foreground = over(rgba(getComputedStyle(element).color), background);
    function luminance(rgb: number[]) {
      return rgb
        .map((channel) => channel / 255)
        .map((value) =>
          value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4,
        )
        .reduce(
          (sum, value, i) => sum + value * [0.2126, 0.7152, 0.0722][i],
          0,
        );
    }
    const light = luminance(foreground),
      dark = luminance(background);
    return (Math.max(light, dark) + 0.05) / (Math.min(light, dark) + 0.05);
  });
}
