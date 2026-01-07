import os
import replicate

from config import COST_PER_MEGAPIXEL_GO_FAST, MEGAPIXELS_1024x1024, REPLICATE_API_TOKEN
from prompts import get_model_optimized_prompt


class ReplicateImageEditor:
    def __init__(self, api_token=REPLICATE_API_TOKEN):
        if not api_token:
            raise ValueError("REPLICATE_API_TOKEN is required")
        self.client = replicate.Client(api_token=api_token)

    def calculate_cost(self, has_input_image=True, model="prunaai/p-image-edit"):
        # Currently only using p-image-edit at $0.01 per image
        return 0.01

        # # Other models (commented out for now):
        # if model == "prunaai/p-image-edit":
        #     return 0.01
        # elif model == "bytedance/seedream-4":
        #     return 0.02
        # elif model == "timothybrooks/instruct-pix2pix":
        #     return 0.015
        # return 0.01

    def edit_image(self, prompt, input_image, model="prunaai/p-image-edit"):
        # Use optimized prompt from prompts.py
        enhanced_prompt = get_model_optimized_prompt(prompt, model)

        try:
            if not input_image:
                raise ValueError("input_image is required for editing")

            # Detect region-based edit - turn off turbo for better precision
            is_region_edit = ' in the ' in prompt.lower()

            input_params = {
                "prompt": enhanced_prompt,
                "turbo": not is_region_edit,
                "aspect_ratio": "match_input_image"
            }
            param_name = "images"

            # # Other models (commented out for future use):
            # elif model == "bytedance/seedream-4":
            #     input_params = {
            #         "prompt": enhanced_prompt,
            #         "size": "2K",
            #         "enhance_prompt": True
            #     }
            #     param_name = "image_input"
            #
            # elif model == "timothybrooks/instruct-pix2pix":
            #     input_params = {
            #         "prompt": enhanced_prompt,
            #         "num_inference_steps": 100,
            #         "guidance_scale": 7.5,
            #         "image_guidance_scale": 1.5
            #     }
            #     param_name = "image"

            # Handle both URL and local file paths
            if isinstance(input_image, str) and input_image.startswith(('http://', 'https://')):
                input_params[param_name] = [input_image]
                output = self.client.run("prunaai/p-image-edit", input=input_params)
            else:
                if not os.path.exists(input_image):
                    raise FileNotFoundError(f"Input image file not found: {input_image}")

                with open(input_image, 'rb') as image_file:
                    input_params[param_name] = [image_file]
                    output = self.client.run("prunaai/p-image-edit", input=input_params)

            # Calculate cost
            cost = self.calculate_cost(has_input_image=True, model=model)

            # Extract image URL from response
            if isinstance(output, list) and len(output) > 0:
                return output[0], cost
            return output, cost

        except FileNotFoundError:
            raise Exception(f"Input image file not found: {input_image}")
        except Exception as e:
            raise Exception(f"Error editing image with p-image-edit: {str(e)}")
