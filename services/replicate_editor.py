import os
import replicate

from config import COST_PER_MEGAPIXEL_GO_FAST, MEGAPIXELS_1024x1024, REPLICATE_API_TOKEN


class ReplicateImageEditor:
    def __init__(self, api_token=REPLICATE_API_TOKEN):
        if not api_token:
            raise ValueError("REPLICATE_API_TOKEN is required")
        self.client = replicate.Client(api_token=api_token)

    def calculate_cost(self, has_input_image=True):
        # P-image-edit costs $0.01 per image
        return 0.01

    def edit_image(self, prompt, input_image):
        # Build the request payload for p-image-edit model.
        # Create detailed instructions to ensure clean, precise, boundary-respecting edits
        enhanced_prompt = (
            f"TASK: {prompt}\n\n"
            "CRITICAL INSTRUCTIONS - FOLLOW EXACTLY:\n\n"
            "1. BOUNDARY CONSTRAINTS (MOST IMPORTANT):\n"
            "   - If the TASK specifies a region, bounded area, or specific location, make changes ONLY within that exact area\n"
            "   - DO NOT make any changes outside the specified region boundaries\n"
            "   - DO NOT modify the background, surrounding objects, or areas not mentioned in the TASK\n"
            "   - Think of the specified region as the ONLY editable zone - everything else is locked and untouchable\n"
            "   - If no specific region is mentioned, only modify the main subject described in the TASK\n\n"
            "2. MINIMAL EDITING APPROACH:\n"
            "   - Make the SMALLEST possible change that fulfills the TASK\n"
            "   - Use subtle, conservative modifications - avoid dramatic or radical changes\n"
            "   - Preserve 95% of the original image - only change what's absolutely necessary\n"
            "   - Keep the original style, lighting, colors, and composition wherever possible\n"
            "   - This is precision editing, not creative reimagining\n\n"
            "3. PRESERVE UNCHANGED AREAS:\n"
            "   - Everything not mentioned in the TASK must remain pixel-perfect identical\n"
            "   - Keep the same background, lighting, shadows, textures, and colors\n"
            "   - Do not reinterpret, enhance, or alter any unchanged areas\n"
            "   - This is an EDIT, not a regeneration - most of the image should be untouched\n\n"
            "4. NO VISUAL OVERLAYS (strictly forbidden):\n"
            "   - NO bounding boxes, rectangles, or outlines\n"
            "   - NO dimension labels or measurements (like '73\"', '17\"')\n"
            "   - NO arrows, pointers, markers, or annotations\n"
            "   - NO text labels, captions, or guides\n"
            "   - NO highlight boxes, selection indicators, or grid lines\n"
            "   - NO debug visualizations or technical graphics\n\n"
            "5. OUTPUT QUALITY:\n"
            "   - Return a clean, photorealistic edited image\n"
            "   - Edits should blend seamlessly and look natural\n"
            "   - No visible seams, artifacts, or indicators of what changed\n"
            "   - Final result should look like an original photograph\n\n"
            "REMEMBER: Less is more. Make minimal, precise changes only within specified boundaries."
        )

        input_params = {
            "prompt": enhanced_prompt,
            "turbo": True,
            "aspect_ratio": "match_input_image"
        }

        try:
            if not input_image:
                raise ValueError("input_image is required for editing")

            # Handle both URL and local file paths for input image
            if isinstance(input_image, str) and input_image.startswith(('http://', 'https://')):
                input_params["images"] = [input_image]  # Array of image URLs
                # Use p-image-edit for image editing
                output = self.client.run(
                    "prunaai/p-image-edit",
                    input=input_params
                )
            else:
                # Validate file exists before opening
                if not os.path.exists(input_image):
                    raise FileNotFoundError(f"Input image file not found: {input_image}")

                # Keep file open during API call to prevent "seek of closed file" error
                with open(input_image, 'rb') as image_file:
                    input_params["images"] = [image_file]  # Array with file handle
                    # Use p-image-edit for image editing
                    output = self.client.run(
                        "prunaai/p-image-edit",
                        input=input_params
                    )

            # Calculate cost for the operation
            cost = self.calculate_cost(has_input_image=True)

            # Extract the image URL from the response
            if isinstance(output, list) and len(output) > 0:
                return output[0], cost
            return output, cost

        except FileNotFoundError:
            raise Exception(f"Input image file not found: {input_image}")
        except Exception as e:
            raise Exception(f"Error editing image with Replicate: {str(e)}")
