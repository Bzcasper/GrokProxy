"""Utility functions for GrokProxy."""


def get_default_user_agent():
    """Get the default user agent string for Grok requests."""
    return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15"


def get_default_chat_payload():
    """Get the default chat payload structure for Grok API."""
    return {
        "temporary": False,
        "modelName": "grok-3",
        "message": "hi",
        "fileAttachments": [],
        "imageAttachments": [],
        "disableSearch": False,
        "enableImageGeneration": True,
        "returnImageBytes": False,
        "returnRawGrokInXaiRequest": False,
        "enableImageStreaming": True,
        "imageGenerationCount": 2,
        "forceConcise": False,
        "toolOverrides": {
            "imageGen": True,
            "webSearch": False,
            "xSearch": False,
            "xMediaSearch": False,
            "trendsSearch": False,
            "xPostAnalyze": False,
        },
        "enableSideBySide": True,
        "isPreset": False,
        "sendFinalMetadata": True,
        "customInstructions": "",
        "deepsearchPreset": "",
        "isReasoning": False,
    }
