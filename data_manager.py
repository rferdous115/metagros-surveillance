import os
import shutil


class DataManager:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def get_classes(self):
        return [d for d in os.listdir(self.data_dir) if os.path.isdir(os.path.join(self.data_dir, d))]

    def add_class(self, class_name):
        path = os.path.join(self.data_dir, class_name)
        if not os.path.exists(path):
            os.makedirs(path)
            return True
        return False
    
    # Alias for API consistency
    create_class = add_class

    def delete_class(self, class_name):
        path = os.path.join(self.data_dir, class_name)
        if os.path.exists(path):
            shutil.rmtree(path)
            return True
        return False

    def save_image(self, image, class_name):
        """Save an image to a class directory.
        
        Note: Requires cv2 to be imported by caller if using OpenCV images.
        """
        import cv2
        class_path = os.path.join(self.data_dir, class_name)
        if not os.path.exists(class_path):
            return False
        
        count = len(os.listdir(class_path))
        filename = f"{class_name}_{count:04d}.jpg"
        cv2.imwrite(os.path.join(class_path, filename), image)
        return True
