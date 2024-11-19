from flask import Flask, request, send_from_directory, jsonify
import os
import base64

app = Flask(__name__)
app.config['IMAGE_FOLDER'] = 'static/images'
app.config['ANNOTATION_FOLDER'] = 'annotations'
os.makedirs(app.config['ANNOTATION_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/images')
def get_images():
    images = sorted([f for f in os.listdir(app.config['IMAGE_FOLDER']) if f.lower().endswith('.png')])
    print(f"Available images: {images}")  # Debugging line
    return jsonify(images)

@app.route('/save_annotation', methods=['POST'])
def save_annotation():
    try:
        data = request.get_json()
        image_name = data['image_name']
        user_hash = data['user_hash']
        mask_data = data['mask']

        # Decode the base64 image
        mask_data = mask_data.split(',')[1]
        mask_image = base64.b64decode(mask_data)

        # Save the mask image
        mask_filename = f"{os.path.splitext(image_name)[0]}_{user_hash}_mask.png"
        mask_path = os.path.join(app.config['ANNOTATION_FOLDER'], mask_filename)
        with open(mask_path, 'wb') as f:
            f.write(mask_image)

        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error in /save_annotation: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    app.run(debug=True)
