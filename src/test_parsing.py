import json
from chat_app import parse_agent_response

def test_parse_agent_response():
    # Test case 1: New list format with answer, products, and image_output
    test_response_1 = '''[
  {
    "answer": "Here are some amazing blue paint options for your project. Could you share the room dimensions or an image of the space to recommend the best choice and quantity?",
    "image_output": "",
    "products": [
      {
        "id": "PROD0022",
        "name": "Frosted Blue",
        "type": "Paint Accessory",
        "description": "A crisp, subtle blue perfect for creating peaceful retreats.",
        "imageURL": "https://staidemodev.blob.core.windows.net/hero-demos-hardcoded-chat-images/FrestedBlue.png",
        "punchLine": "Chill out in classic blue",
        "price": "$48.99"
      }
    ]
  }
]'''
    
    result_1 = parse_agent_response(test_response_1)
    print("Test 1 - List format:")
    print(f"Answer: {result_1['answer']}")
    print(f"Products: {result_1['products']}")
    print(f"Image URL: {result_1['image_url']}")
    print(f"Agent: {result_1['agent']}")
    print()
    
    # Test case 2: Old dict format
    test_response_2 = '''{
        "answer": "This is a test answer",
        "agent": "test_agent",
        "products": "test_products",
        "image_url": "test_image.jpg"
    }'''
    
    result_2 = parse_agent_response(test_response_2)
    print("Test 2 - Dict format:")
    print(f"Answer: {result_2['answer']}")
    print(f"Products: {result_2['products']}")
    print(f"Image URL: {result_2['image_url']}")
    print(f"Agent: {result_2['agent']}")
    print()
    
    # Test case 3: Plain string (not JSON)
    test_response_3 = "This is a plain text response"
    
    result_3 = parse_agent_response(test_response_3)
    print("Test 3 - Plain string:")
    print(f"Answer: {result_3['answer']}")
    print(f"Products: {result_3['products']}")
    print(f"Image URL: {result_3['image_url']}")
    print(f"Agent: {result_3['agent']}")
    print()
    
    # Test case 4: List with non-dict first item
    test_response_4 = '["simple string in list"]'
    
    result_4 = parse_agent_response(test_response_4)
    print("Test 4 - List with non-dict item:")
    print(f"Answer: {result_4['answer']}")
    print(f"Products: {result_4['products']}")
    print(f"Image URL: {result_4['image_url']}")
    print(f"Agent: {result_4['agent']}")

if __name__ == "__main__":
    test_parse_agent_response() 