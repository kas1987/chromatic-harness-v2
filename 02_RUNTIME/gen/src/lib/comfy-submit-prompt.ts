const comfyUrl = () => process.env.GEN_COMFY_URL || 'http://127.0.0.1:8188';

/**
 * POST workflow to ComfyUI /prompt; returns Comfy prompt_id.
 */
export async function submitComfyPrompt(
  workflow: Record<string, unknown>,
  clientId: string,
): Promise<string> {
  const payload = JSON.stringify({
    prompt: workflow,
    client_id: clientId,
  });

  try {
    const response = await fetch(`${comfyUrl()}/prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
    });

    if (!response.ok) {
      throw new Error(`ComfyUI API error: ${response.status} ${response.statusText}`);
    }

    const data = (await response.json()) as { prompt_id: string };
    return data.prompt_id;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const wrapped = new Error(`Failed to submit to ComfyUI: ${message}`);
    Object.assign(wrapped, { cause: err });
    throw wrapped;
  }
}
