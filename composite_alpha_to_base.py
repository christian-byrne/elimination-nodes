import torch
import os
import hashlib
from torchvision import transforms
from typing import Tuple, Union

from PIL import Image, ImageOps, ImageSequence, ImageDraw
import numpy as np
import cv2
import pickle
from typing import List, Union
from skimage import img_as_float, img_as_ubyte

from utils.tensor_utils import TensorImgUtils
from transform.scale import ImageScaler
from equalize.equalize_size import SizeMatcher


# sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "comfy"))

import folder_paths

# class Example:
#     """
#     A example node

#     Class methods
#     -------------
#     INPUT_TYPES (dict):
#         Tell the main program input parameters of nodes.
#     IS_CHANGED:
#         optional method to control when the node is re executed.

#     Attributes
#     ----------
#     RETURN_TYPES (`tuple`):
#         The type of each element in the output tulple.
#     RETURN_NAMES (`tuple`):
#         Optional: The name of each output in the output tulple.
#     FUNCTION (`str`):
#         The name of the entry-point method. For example, if `FUNCTION = "execute"` then it will run Example().execute()
#     OUTPUT_NODE ([`bool`]):
#         If this node is an output node that outputs a result/image from the graph. The SaveImage node is an example.
#         The backend iterates on these output nodes and tries to execute all their parents if their parent graph is properly connected.
#         Assumed to be False if not present.
#     CATEGORY (`str`):
#         The category the node should appear in the UI.
#     execute(s) -> tuple || None:
#         The entry point method. The name of this method must be the same as the value of property `FUNCTION`.
#         For example, if `FUNCTION = "execute"` then this method's name must be `execute`, if `FUNCTION = "foo"` then it must be `foo`.
#     """
#     def __init__(self):
#         pass

#     @classmethod
#     def INPUT_TYPES(s):
#         """
#             Return a dictionary which contains config for all input fields.
#             Some types (string): "MODEL", "VAE", "CLIP", "CONDITIONING", "LATENT", "IMAGE", "INT", "STRING", "FLOAT".
#             Input types "INT", "STRING" or "FLOAT" are special values for fields on the node.
#             The type can be a list for selection.

#             Returns: `dict`:
#                 - Key input_fields_group (`string`): Can be either required, hidden or optional. A node class must have property `required`
#                 - Value input_fields (`dict`): Contains input fields config:
#                     * Key field_name (`string`): Name of a entry-point method's argument
#                     * Value field_config (`tuple`):
#                         + First value is a string indicate the type of field or a list for selection.
#                         + Secound value is a config for type "INT", "STRING" or "FLOAT".
#         """
#         return {
#             "required": {
#                 "image": ("IMAGE",),
#                 "int_field": ("INT", {
#                     "default": 0,
#                     "min": 0, #Minimum value
#                     "max": 4096, #Maximum value
#                     "step": 64, #Slider's step
#                     "display": "number" # Cosmetic only: display as "number" or "slider"
#                 }),
#                 "float_field": ("FLOAT", {
#                     "default": 1.0,
#                     "min": 0.0,
#                     "max": 10.0,
#                     "step": 0.01,
#                     "round": 0.001, #The value represeting the precision to round to, will be set to the step value by default. Can be set to False to disable rounding.
#                     "display": "number"}),
#                 "print_to_screen": (["enable", "disable"],),
#                 "string_field": ("STRING", {
#                     "multiline": False, #True if you want the field to look like the one on the ClipTextEncode node
#                     "default": "Hello World!"
#                 }),
#             },
#         }

#     RETURN_TYPES = ("IMAGE",)
#     #RETURN_NAMES = ("image_output_name",)

#     FUNCTION = "test"

#     #OUTPUT_NODE = False

#     CATEGORY = "Example"

#     def test(self, image, string_field, int_field, float_field, print_to_screen):
#         if print_to_screen == "enable":
#             print(f"""Your input contains:
#                 string_field aka input text: {string_field}
#                 int_field: {int_field}
#                 float_field: {float_field}
#             """)
#         #do some processing on the image, in this example I just invert it
#         image = 1.0 - image
#         return (image,)

#     """
#         The node will always be re executed if any of the inputs change but
#         this method can be used to force the node to execute again even when the inputs don't change.
#         You can make this node return a number or a string. This value will be compared to the one returned the last time the node was
#         executed, if it is different the node will be executed again.
#         This method is used in the core repo for the LoadImage node where they return the image hash as a string, if the image hash
#         changes between executions the LoadImage node is executed again.
#     """
#     #@classmethod
#     #def IS_CHANGED(s, image, string_field, int_field, float_field, print_to_screen):
#     #    return ""

# # Set the web directory, any .js file in that directory will be loaded by the frontend as a frontend extension
# # WEB_DIRECTORY = "./somejs"

# # A dictionary that contains all nodes you want to export with their names
# # NOTE: names should be globally unique
# NODE_CLASS_MAPPINGS = {
#     "Example": Example
# }

# # A dictionary that contains the friendly/humanly readable titles for the nodes
# NODE_DISPLAY_NAME_MAPPINGS = {
#     "Example": "Example Node"
# }


class CompositeAlphaToBase:
    def __init__(self):
        CATEGORY = "image"
        RETURN_TYPES = ("IMAGE",)
        FUNCTION = "composite"

    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        # files = [
        #     f
        #     for f in os.listdir(input_dir)
        #     if os.path.isfile(os.path.join(input_dir, f))
        # ]
        return {
            "required": {
                # "base_image": (sorted(files), {"image_upload": True}),
                # "alpha_overlay": (sorted(files), {"image_upload": True}),
                "base_image": ("IMAGE",),
                "alpha_overlay": ("IMAGE",),
                "size_matching_method": (["fit_center_and_pad", "cover_maintain_aspect_ratio_with_crop", "cover_perfect_by_distorting", "crop_larger_to_match"],),
            },
        }


    def composite(self, base_image: torch.Tensor, alpha_overlay: torch.Tensor, size_matching_method: str = "cover_and_crop") -> Tuple[torch.Tensor]:
        base_image = base_image.unsqueeze(0)
        alpha_overlay = alpha_overlay.unsqueeze(0)

        size_matcher = SizeMatcher()
        if size_matching_method == "fit_center_and_pad":            
            base_image, alpha_overlay = size_matcher.fit_maintain_pad(
                base_image, alpha_overlay
            )
        elif size_matching_method == "cover_maintain_aspect_ratio_with_crop":
            base_image, alpha_overlay = size_matcher.cover_maintain(
                base_image, alpha_overlay
            )
        elif size_matching_method == "cover_perfect_by_distorting":
            base_image, alpha_overlay = size_matcher.cover_distort(
                base_image, alpha_overlay
            )
        elif size_matching_method == "crop_to_match":
            base_image, alpha_overlay = size_matcher.crop_larger_to_match(
                base_image, alpha_overlay
            ) 

