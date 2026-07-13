import os
import logging

logger = logging.getLogger(__name__)


def setup_huggingface_mirror():
    mirror_url = os.getenv('HF_ENDPOINT', 'https://hf-mirror.com')
    os.environ['HF_ENDPOINT'] = mirror_url
    logger.info(f"HuggingFace mirror set to: {mirror_url}")


def download_ai_model(model_name="Qwen/Qwen2-1.5B-Instruct"):
    setup_huggingface_mirror()
    
    try:
        logger.info(f"Checking AI model: {model_name}")
        
        from transformers import AutoTokenizer, AutoModelForCausalLM
        
        logger.info(f"Downloading tokenizer for {model_name}...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_name, 
            trust_remote_code=True,
            resume_download=True
        )
        logger.info("Tokenizer downloaded successfully")
        
        logger.info(f"Downloading model for {model_name}...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto",
            trust_remote_code=True,
            resume_download=True
        )
        logger.info("Model downloaded successfully")
        
        return True
    except Exception as e:
        logger.error(f"Failed to download AI model: {e}")
        logger.warning("AI analysis will use fallback mode")
        return False


def preload_models():
    logger.info("=" * 50)
    logger.info("Starting model preloading...")
    logger.info("=" * 50)
    
    ai_model_success = download_ai_model()
    
    if ai_model_success:
        logger.info("AI model preloaded successfully")
    else:
        logger.warning("AI model preload failed, will use fallback analysis")
    
    logger.info("=" * 50)
    logger.info("Model preloading completed")
    logger.info("=" * 50)
    
    return ai_model_success


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    preload_models()