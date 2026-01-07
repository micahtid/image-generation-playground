# Optimized prompts for p-image-edit
# Key: "maintaining the same" tells model to preserve unmentioned attributes

def get_editing_prompt(user_task):
    return f"{user_task}, maintaining the same style, color, size, shape, font, case, position, lighting, and background for everything not explicitly changed"


def get_model_optimized_prompt(user_task, model):
    return get_editing_prompt(user_task)
