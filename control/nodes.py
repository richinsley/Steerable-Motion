import numpy as np

import folder_paths

from .control import ControlNetAdvancedImport, T2IAdapterAdvancedImport, load_controlnet, ControlNetWeightsTypeImport, T2IAdapterWeightsTypeImport,\
    LatentKeyframeGroupImport, TimestepKeyframeImport, TimestepKeyframeGroupImport, is_advanced_controlnet
from .weight_nodes import ScaledSoftControlNetWeightsImport, SoftControlNetWeightsImport, CustomControlNetWeightsImport, \
    SoftT2IAdapterWeightsImport, CustomT2IAdapterWeightsImport
from .latent_keyframe_nodes import LatentKeyframeGroupNodeImport, LatentKeyframeInterpolationNodeImport, LatentKeyframeBatchedGroupNodeImport, LatentKeyframeNodeImport
from .deprecated_nodes import LoadImagesFromDirectory
from .logger import logger


class TimestepKeyframeNodeImport:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "start_percent": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.001}, ),
            },
            "optional": {
                "control_net_weights": ("CONTROL_NET_WEIGHTS", ),
                "t2i_adapter_weights": ("T2I_ADAPTER_WEIGHTS", ),
                "latent_keyframe": ("LATENT_KEYFRAME", ),
                "prev_timestep_keyframe": ("TIMESTEP_KEYFRAME", ),                
            }
        }
    
    RETURN_TYPES = ("TIMESTEP_KEYFRAME", )
    FUNCTION = "load_keyframe"

    CATEGORY = "Adv-ControlNet 🛂🅐🅒🅝/keyframes"

    def load_keyframe(self,
                      start_percent: float,
                      control_net_weights: ControlNetWeightsTypeImport=None,
                      t2i_adapter_weights: T2IAdapterWeightsTypeImport=None,
                      latent_keyframe: LatentKeyframeGroupImport=None,
                      prev_timestep_keyframe: TimestepKeyframeGroupImport=None):
        if not prev_timestep_keyframe:
            prev_timestep_keyframe = TimestepKeyframeGroupImport()
        keyframe = TimestepKeyframeImport(start_percent, control_net_weights, t2i_adapter_weights, latent_keyframe)
        prev_timestep_keyframe.add(keyframe)
        return (prev_timestep_keyframe,)


class ControlNetLoaderAdvancedImport:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "control_net_name": (folder_paths.get_filename_list("controlnet"), ),
            },
            "optional": {
                "timestep_keyframe": ("TIMESTEP_KEYFRAME", ),
            }
        }
    
    RETURN_TYPES = ("CONTROL_NET", )
    FUNCTION = "load_controlnet"

    CATEGORY = "Adv-ControlNet 🛂🅐🅒🅝/loaders"

    def load_controlnet(self, control_net_name, timestep_keyframe: TimestepKeyframeGroupImport=None):
        controlnet_path = folder_paths.get_full_path("controlnet", control_net_name)
        controlnet = load_controlnet(controlnet_path, timestep_keyframe)
        return (controlnet,)
    

class DiffControlNetLoaderAdvancedImport:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": ("MODEL",),
                "control_net_name": (folder_paths.get_filename_list("controlnet"), )
            },
            "optional": {
                "timestep_keyframe": ("TIMESTEP_KEYFRAME", ),
            }
        }
    
    RETURN_TYPES = ("CONTROL_NET", )
    FUNCTION = "load_controlnet"

    CATEGORY = "Adv-ControlNet 🛂🅐🅒🅝/loaders"

    def load_controlnet(self, control_net_name, timestep_keyframe: TimestepKeyframeGroupImport, model):
        controlnet_path = folder_paths.get_full_path("controlnet", control_net_name)
        controlnet = load_controlnet(controlnet_path, timestep_keyframe, model)
        return (controlnet,)


class AdvancedControlNetApplyImport:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "positive": ("CONDITIONING", ),
                "negative": ("CONDITIONING", ),
                "control_net": ("CONTROL_NET", ),
                "image": ("IMAGE", ),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.01}),
                "start_percent": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.001}),
                "end_percent": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.001})
            },
            "optional": {
                "mask_optional": ("MASK", ),
            }
        }

    RETURN_TYPES = ("CONDITIONING","CONDITIONING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "apply_controlnet"

    CATEGORY = "Adv-ControlNet 🛂🅐🅒🅝/conditioning"

    def apply_controlnet(self, positive, negative, control_net, image, strength, start_percent, end_percent, mask_optional=None):
        if strength == 0:
            return (positive, negative)

        control_hint = image.movedim(-1,1)
        cnets = {}

        out = []
        for conditioning in [positive, negative]:
            c = []
                        
            for t in conditioning:
                d = t[1].copy()

                prev_cnet = d.get('control', None)
                if prev_cnet in cnets:
                    c_net = cnets[prev_cnet]
                    
                else:
                    c_net = control_net.copy().set_cond_hint(control_hint, strength, (1.0 - start_percent, 1.0 - end_percent))
                    # set cond hint mask
                    if mask_optional is not None:
                        if is_advanced_controlnet(c_net):
                            # if not in the form of a batch, make it so
                            if len(mask_optional.shape) < 3:
                                mask_optional = mask_optional.unsqueeze(0)
                            c_net.set_cond_hint_mask(mask_optional)
                    c_net.set_previous_controlnet(prev_cnet)
                    cnets[prev_cnet] = c_net

                d['control'] = c_net
                d['control_apply_to_uncond'] = False
                n = [t[0], d]
                c.append(n)
            out.append(c)
        return (out[0], out[1])

class BatchCreativeInterpolationNode:
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "positive": ("CONDITIONING", ),
                "negative": ("CONDITIONING", ),
                "control_net_name": (folder_paths.get_filename_list("controlnet"), ),
                "images": ("IMAGE", ),
                "type_of_frame_distribution": (["linear", "dynamic"],),
                "linear_frames_per_keyframe": ("INT", {"default": 16, "min": 4, "max": 64, "step": 1}),                
                "dynamic_frames_per_keyframe": ("STRING", {"multiline": True, "default": "0,10,26,40"}),
                "length_of_key_frame_influence": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.001}),
                "cn_strength": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),      
                "soft_scaled_cn_weights_multiplier": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 10.0, "step": 0.01}),          
                "interpolation": (["ease-in", "ease-out", "ease-in-out"],),
                "buffer": ("INT", {"default": 4, "min": 0, "max": 16, "step": 1}),
            },
            "optional": {
            }
        }

    RETURN_TYPES = ("CONDITIONING","CONDITIONING")
    RETURN_NAMES = ("positive", "negative")
    FUNCTION = "combined_function"

    CATEGORY = "ComfyUI-Creative-Interpolation 🎞️🅟🅞🅜/Interpolation"

    def combined_function(self, positive, negative, control_net_name, images,type_of_frame_distribution,linear_frames_per_keyframe,dynamic_frames_per_keyframe,length_of_key_frame_influence,cn_strength,soft_scaled_cn_weights_multiplier,interpolation,buffer):
        
        def calculate_dynamic_influence_ranges(keyframe_positions, length_of_influence):
            if len(keyframe_positions) < 2:
                return []

            influence_ranges = []
            for i, position in enumerate(keyframe_positions):
                prev_position = keyframe_positions[i - 1] if i > 0 else position
                next_position = keyframe_positions[i + 1] if i < len(keyframe_positions) - 1 else position

                half_prev_distance = (position - prev_position) * length_of_influence / 2
                half_next_distance = (next_position - position) * length_of_influence / 2

                start_influence = max(0, int(position - half_prev_distance))
                end_influence = min(keyframe_positions[-1], int(position + half_next_distance))

                influence_ranges.append((start_influence, end_influence))

            return influence_ranges

        def add_starting_buffer(influence_ranges, buffer=4):
            shifted_ranges = [(0, buffer)]
            for start, end in influence_ranges:
                shifted_ranges.append((start + buffer, end + buffer))
            return shifted_ranges
        
        def get_keyframe_positions(type_of_frame_distribution, dynamic_frames_per_keyframe, images, linear_frames_per_keyframe):
            if type_of_frame_distribution == "dynamic":
                # Sort the keyframe positions in numerical order
                return sorted([int(kf.strip()) for kf in dynamic_frames_per_keyframe.split(',')])
            else:
                # Calculate the number of keyframes based on the total duration and linear_frames_per_keyframe
                return [i * linear_frames_per_keyframe for i in range(len(images))]
 
        keyframe_positions = get_keyframe_positions(type_of_frame_distribution, dynamic_frames_per_keyframe, images, linear_frames_per_keyframe)
                
        inluence_ranges = calculate_dynamic_influence_ranges(keyframe_positions,length_of_key_frame_influence)

        influence_ranges = add_starting_buffer(inluence_ranges, buffer)

        for i, (start, end) in enumerate(influence_ranges):
            
            batch_index_from, batch_index_to_excl = influence_ranges[i]
                                                                                                
            if i == 0:  # buffer image
                image = images[0]
                strength_from = 1.0
                strength_to = 1.0            
                return_at_midpoint = False 
            elif i == 1: # First image
                image = images[0]
                strength_from = 1.0
                strength_to = 0.0
                return_at_midpoint = False                            
            elif i == len(images) - 1:  # Last image
                image = images[i-1]
                strength_from = 0.0
                strength_to = 1.0
                return_at_midpoint = False                                
            else:  # Middle images
                image = images[i-1]
                strength_from = 0.0
                strength_to = 1.0
                return_at_midpoint = True
                                                                                                              
            latent_keyframe_interpolation_node = LatentKeyframeInterpolationNodeImport()
            latent_keyframe, = latent_keyframe_interpolation_node.load_keyframe(
                batch_index_from,
                strength_from,
                batch_index_to_excl,
                strength_to,
                interpolation,
                return_at_midpoint)                        
                
            scaled_soft_control_net_weights = ScaledSoftControlNetWeightsImport()
            control_net_weights, _ = scaled_soft_control_net_weights.load_weights(
                soft_scaled_cn_weights_multiplier,
                False)


            timestep_keyframe_node = TimestepKeyframeNodeImport()
            timestep_keyframe, = timestep_keyframe_node.load_keyframe(
                start_percent=0.0,
                control_net_weights=control_net_weights,
                t2i_adapter_weights=None,
                latent_keyframe=latent_keyframe,
                prev_timestep_keyframe=None
            )

            control_net_loader = ControlNetLoaderAdvancedImport()
            control_net, = control_net_loader.load_controlnet(
                control_net_name, 
                timestep_keyframe)

            apply_advanced_control_net = AdvancedControlNetApplyImport()                                    
            positive, negative = apply_advanced_control_net.apply_controlnet(
                positive,
                negative,
                control_net,
                image.unsqueeze(0),
                cn_strength,
                0.0,
                1.0)

        return (positive, negative)

# NODE MAPPING
NODE_CLASS_MAPPINGS = {
    # Combined
    "BatchCreativeInterpolation": BatchCreativeInterpolationNode
    # Keyframes
    # "TimestepKeyframe": TimestepKeyframeNodeImport,
    # "LatentKeyframeImport": LatentKeyframeNodeImport,
    # "LatentKeyframeGroupImport": LatentKeyframeGroupImportNode,
    # "LatentKeyframeBatchedGroupImport": LatentKeyframeBatchedGroupNodeImport,
    # "LatentKeyframeTiming": LatentKeyframeInterpolationNodeImport,
    # Loaders
    # "ControlNetLoaderAdvancedImport": ControlNetLoaderAdvancedImport,
    # "DiffControlNetLoaderAdvancedImport": DiffControlNetLoaderAdvancedImport,
    # Conditioning
    # "ACN_AdvancedControlNetApplyImport": AdvancedControlNetApplyImport,
    # Weights
    # "ScaledSoftControlNetWeightsImport": ScaledSoftControlNetWeightsImport,
    # "SoftControlNetWeights": SoftControlNetWeights,
    # "CustomControlNetWeights": CustomControlNetWeights,
    # "SoftT2IAdapterWeights": SoftT2IAdapterWeights,
    # "CustomT2IAdapterWeights": CustomT2IAdapterWeights,
    # Image
    # "LoadImagesFromDirectory": LoadImagesFromDirectory
}

NODE_DISPLAY_NAME_MAPPINGS = {
    # Combined
    "BatchCreativeInterpolation": "Batch Creative Interpolation 🎞️🅟🅞🅜"
    # Keyframes
    # "TimestepKeyframe": "Timestep Keyframe 🎞️🅟🅞🅜",
    # "LatentKeyframe": "Latent Keyframe 🛂🅐🅒🅝",
    # "LatentKeyframeGroupImport": "Latent Keyframe Group 🛂🅐🅒🅝",
    # "LatentKeyframeBatchedGroup": "Latent Keyframe Batched Group 🛂🅐🅒🅝",
    # "LatentKeyframeTiming": "Latent Keyframe Interpolation 🛂🅐🅒🅝",
    # Loaders
    # "ControlNetLoaderAdvancedImport": "Load ControlNet Model (Advanced) 🛂🅐🅒🅝",
    # "DiffControlNetLoaderAdvancedImport": "Load ControlNet Model (diff Advanced) 🛂🅐🅒🅝",
    # Conditioning
    # "ACN_AdvancedControlNetApplyImport": "Apply Advanced ControlNet 🛂🅐🅒🅝",
    # Weights
    # "ScaledSoftControlNetWeightsImport": "Scaled Soft ControlNet Weights 🛂🅐🅒🅝",
    # "SoftControlNetWeights": "Soft ControlNet Weights 🛂🅐🅒🅝",
    # "CustomControlNetWeights": "Custom ControlNet Weights 🛂🅐🅒🅝",
    # "SoftT2IAdapterWeights": "Soft T2IAdapter Weights 🛂🅐🅒🅝",
    # "CustomT2IAdapterWeights": "Custom T2IAdapter Weights 🛂🅐🅒🅝",
    # Image
    # "LoadImagesFromDirectory": "Load Images [DEPRECATED] 🛂🅐🅒🅝"
}
