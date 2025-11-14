import json
import re

def extract_bot_reply(msg) -> str:
    """Extract the bot reply from the agent processor message."""
    msg = str(msg)
    match = re.search(r"'value':\s*'([^']*)'", msg)
    if match:
        result = match.group(1)
        return result
    return msg

def parse_agent_response(response: str) -> dict:
    """
    Parse agent response to check if it's JSON format.
    Handles JSON inside code blocks (```json ... ```),
    both objects and arrays, and also plain JSON strings.
    If it's JSON, map the fields accordingly.
    If it's not JSON, return it as "answer" with other fields empty.
    """
    # Try to extract JSON (object or array) from code block
    codeblock_match = re.search(r'```(?:json)?\s*([\[{].*[\]}])\s*```', response, re.DOTALL)
    if codeblock_match:
        response = codeblock_match.group(1).strip()
    else:
        # If not in code block, try to extract a JSON object or array from the string
        json_match = re.search(r'([\[{].*[\]}])', response, re.DOTALL)
        if json_match:
            response = json_match.group(1).strip()
    try:
        parsed_response = json.loads(response)
        if isinstance(parsed_response, list) and len(parsed_response) > 0:
            first_item = parsed_response[0]
            if isinstance(first_item, dict):
                answer = first_item.get("answer", "")
                products = first_item.get("products", "")
                image_output = first_item.get("image_output", "")
                discount_percentage = first_item.get("discount_percentage", "")
                cart = first_item.get("cart", [])
                if products and not isinstance(products, str):
                    products = json.dumps(products)
                return {
                    "answer": answer,
                    "agent": "",
                    "products": products,
                    "discount_percentage": str(discount_percentage) if discount_percentage else "",
                    "image_url": image_output,
                    "video_url": "",
                    "additional_data": "",
                    "cart": cart
                }
            else:
                return {
                    "answer": str(parsed_response),
                    "agent": "",
                    "products": "",
                    "discount_percentage": "",
                    "image_url": "",
                    "video_url": "",
                    "additional_data": ""
                }
        elif isinstance(parsed_response, dict):
            answer = parsed_response.get("answer", "")
            if isinstance(answer, str) and answer.startswith('[') and answer.endswith(']'):
                try:
                    nested_json = json.loads(answer)
                    if isinstance(nested_json, list) and len(nested_json) > 0:
                        first_item = nested_json[0]
                        if isinstance(first_item, dict) and "answer" in first_item:
                            answer = first_item["answer"]
                except json.JSONDecodeError:
                    pass
            return {
                "answer": answer,
                "agent": parsed_response.get("agent", ""),
                "products": parsed_response.get("products", ""),
                "discount_percentage": str(parsed_response.get("discount_percentage", "")) if parsed_response.get("discount_percentage") else "",
                "image_url": parsed_response.get("image_url", ""),
                "video_url": parsed_response.get("video_url", ""),
                "additional_data": parsed_response.get("additional_data", ""),
                "cart": parsed_response.get("cart", [])
            }
        else:
            return {
                "answer": str(parsed_response),
                "agent": "",
                "products": "",
                "discount_percentage": "",
                "image_url": "",
                "video_url": "",
                "additional_data": "",
                "cart": []
            }
    except (json.JSONDecodeError, TypeError) as e:
        return {
            "answer": str(response),
            "agent": "",
            "products": "",
            "discount_percentage": "",
            "image_url": "",
            "video_url": "",
            "additional_data": "",
            "cart": []
        }

def merge_cart_and_cora(cart_reply_raw: str, cora_reply_raw: str) -> dict:
    """
    Merge cart and cora responses:
    - answer and image_output from cora
    - products from cart (as a list)
    Handles code blocks and JSON parsing robustly.
    """
    # Parse cart products (should be a list)
    cart_products = []
    # Try to extract JSON (object or array) from code block
    cart_codeblock_match = re.search(r'```(?:json)?\s*([\[{].*[\]}])\s*```', cart_reply_raw, re.DOTALL)
    if cart_codeblock_match:
        cart_json_str = cart_codeblock_match.group(1).strip()
    else:
        cart_json_match = re.search(r'([\[{].*[\]}])', cart_reply_raw, re.DOTALL)
        if cart_json_match:
            cart_json_str = cart_json_match.group(1).strip()
        else:
            cart_json_str = cart_reply_raw
    try:
        cart_parsed = json.loads(cart_json_str)
        # Handle both direct list and object with cart property
        if isinstance(cart_parsed, list):
            cart_products = cart_parsed
        elif isinstance(cart_parsed, dict) and "cart" in cart_parsed:
            cart_products = cart_parsed["cart"]
        else:
            cart_products = []
    except Exception:
        cart_products = []

    # Parse cora reply (should be a dict)
    cora_json = parse_agent_response(cora_reply_raw)
    # If parse_agent_response returns products as a string, ignore it
    merged = {
        "answer": cora_json.get("answer", ""),
        "image_output": cora_json.get("image_output", []),
        "cart": cart_products
    }
    return merged 