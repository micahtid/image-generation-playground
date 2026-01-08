import os
import replicate

from config import COST_PER_MEGAPIXEL_GO_FAST, MEGAPIXELS_1024x1024, REPLICATE_API_TOKEN


class ImageGenerator:
    def __init__(self, api_token=REPLICATE_API_TOKEN):
        if not api_token:
            raise ValueError("REPLICATE_API_TOKEN is required")
        self.client = replicate.Client(api_token=api_token)

    def calculate_cost(self, has_input_image=False):
        # Estimate cost for input + output based on megapixels.
        # Using 896x896 = 0.8 megapixels instead of 1024x1024 = 1.0 megapixels
        megapixels = 0.8
        output_cost = megapixels * COST_PER_MEGAPIXEL_GO_FAST
        input_cost = megapixels * COST_PER_MEGAPIXEL_GO_FAST if has_input_image else 0
        return input_cost + output_cost

    def generate_image(self, prompt, input_image=None):
        # Build the request payload for the image model.
        # Using 896x896 instead of 1024x1024 for ~25% cost reduction
        input_params = {
            "prompt": prompt,
            "go_fast": True,
            "output_format": "png",
            "output_quality": 90,
            "width": 896,
            "height": 896
        }

        try:
            if input_image:
                if isinstance(input_image, str) and input_image.startswith(('http://', 'https://')):
                    input_params["input_images"] = [input_image]
                    output = self.client.run(
                        "black-forest-labs/flux-2-dev",
                        input=input_params
                    )
                else:
                    # Validate file exists before opening
                    if not os.path.exists(input_image):
                        raise FileNotFoundError(f"Input image file not found: {input_image}")

                    with open(input_image, 'rb') as image_file:
                        input_params["input_images"] = [image_file]
                        output = self.client.run(
                            "black-forest-labs/flux-2-dev",
                            input=input_params
                        )
            else:
                output = self.client.run(
                    "black-forest-labs/flux-2-dev",
                    input=input_params
                )

            if isinstance(output, list) and len(output) > 0:
                return output[0]
            return output

        except FileNotFoundError as e:
            raise Exception(str(e))
        except Exception as e:
            raise Exception(f"Error generating image: {str(e)}")
