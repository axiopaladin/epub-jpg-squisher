#!python3
from ebooklib import epub
from pathlib import Path
from PIL import Image
import subprocess
import sys
import tempfile
_EIMG = epub.EpubCover | epub.EpubImage

DEV_HEIGHT = 800
DEV_WIDTH = 480
SMALL_IMG = 128

class ParsedEpub:
    def __init__(self, book: epub.EpubBook) -> None:
        self.epub = book
        self.cover:  list[int] = []
        self.images: list[int] = []
        self.docs: list[int] = []
        self.namechanges: list[tuple[str, str]] = []
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Get indices of various items from original book
        for i, item in enumerate(book.items):
            if isinstance(item, epub.EpubCover):
                self.cover.append(i)
            if isinstance(item, epub.EpubImage):
                self.images.append(i)
            if isinstance(item, epub.EpubHtml):
                self.docs.append(i)
        
        # Warn if more than 1 cover item
        if len(self.cover) > 1:
            print(f"WARNING: Multiple covers detected. Found {len(self.cover)}:")
            for idx in self.cover:
                print(f" - {self.epub.items[idx].file_name}")
    
    def make_epub_img(self, orig_item: _EIMG) -> _EIMG:
        # Create container
        file_name, contents = self.convert_img(orig_item)
        if isinstance(orig_item, epub.EpubCover):
            new_item = epub.EpubCover(uid=file_name.name, file_name=str(file_name))
        else:
            new_item = epub.EpubImage(uid=file_name.name, file_name=str(file_name))
        new_item.media_type = 'image/jpeg'
        new_item.set_content(contents)
        
        # Track metadata about conversion
        if new_item.file_name != orig_item.file_name:
            self.namechanges.append((orig_item.file_name, new_item.file_name))
            print(f"*** Compressed {orig_item.file_name} to {new_item.file_name} successfully")
        return new_item
    
    def convert_img(self, image: _EIMG) -> tuple[Path, bytes]:
        # Create some working paths on disk
        epath = Path(image.file_name)
        orig_image = self.temp_dir / epath.name
        if epath.suffix.lower() == ".jpg":
            new_image = self.temp_dir / ("eink_" + epath.name)
        else:
            new_image = self.temp_dir / (epath.stem + ".jpg")
        
        # Dump image data to disk
        with open(orig_image, "wb") as file:
            file.write(image.content)
        command: list[str|Path] = ['convert', orig_image]
        
        # Check dimensions and prepare to rotate/resize if necessary
        im_file = Image.open(orig_image)
        isCover = isinstance(image, epub.EpubCover)
        rotate = (im_file.width < im_file.height
                 and max(im_file.size) > SMALL_IMG # skip small decorative images
                 and not isCover) # never rotate cover image
        if rotate or isCover:
            if im_file.width > DEV_WIDTH or im_file.height > DEV_HEIGHT:
                command += ['-resize', f'{DEV_WIDTH}x{DEV_HEIGHT}>']
            if rotate:
                command += ['-rotate', '90']
        else:
            if im_file.width > DEV_HEIGHT or im_file.height > DEV_WIDTH:
                command += ['-resize', f'{DEV_HEIGHT}x{DEV_WIDTH}']
        
        # Recolor non-cover images
        if not isCover:
            command += ['-colorspace', 'Gray', '-dither', 'FloydSteinberg', '-colors', '3']
        
        # Squish with imagemagick
        magick = subprocess.run(command + [new_image])
        magick.check_returncode() # throw an error if conversion fails
        
        # Read output file
        with open(new_image, "rb") as file:
            return (epath.parent / new_image.name), file.read()
    
    def make_epub_html(self, orig_item: epub.EpubHtml) -> epub.EpubHtml:
        text: str = orig_item.get_content().decode()
        for oldname, newname in self.namechanges:
            if oldname in text:
                text = text.replace(oldname, newname)
        new_item = epub.EpubHtml(
            uid=orig_item.id,
            file_name=orig_item.file_name,
            media_type=orig_item.media_type,
            title=orig_item.title,
            lang=orig_item.lang,
            direction=orig_item.direction,
            media_overlay=orig_item.media_overlay,
            media_duration=orig_item.media_duration
        )
        new_item.set_content(text.encode('utf-8'))
        return new_item
    
    def export_epub(self, output_file: str) -> bool:
        try:
            # Bare bones metadata
            new_book = epub.EpubBook()
            new_book.set_title(self.epub.title)
            new_book.set_language(self.epub.language)
            if self.epub.direction:
                new_book.set_direction(self.epub.direction)
            if self.epub.uid:
                new_book.set_identifier(self.epub.uid)
            new_book.metadata = self.epub.metadata
            
            # Process all images
            new_images: dict[int, _EIMG] = {}
            for idx in (self.cover + self.images):
                new_images[idx] = self.make_epub_img(self.epub.items[idx])
            
            # Process all HTML
            new_html: dict[int, epub.EpubHtml] = {}
            for idx in self.docs:
                new_html[idx] = self.make_epub_html(self.epub.items[idx])
            
            # Write content to new epub
            for i, item in enumerate(self.epub.items):
                if isinstance(item, _EIMG):
                    new_book.add_item(new_images[i])
                elif isinstance(item, epub.EpubHtml):
                    new_book.add_item(new_html[i])
                else:
                    new_book.add_item(item)
            
            # Match deeper fancy metadata stuff
            new_book.spine = self.epub.spine
            new_book.guide = self.epub.guide
            new_book.pages = self.epub.pages
            # new_book.toc = self.epub.toc
                # Not sure how to reconstruct toc. Naive copy like this doesn't work
            new_book.bindings = self.epub.bindings
            new_book.direction = self.epub.direction
            new_book.templates = self.epub.templates
            new_book.prefixes = self.epub.prefixes
            new_book.namespaces = self.epub.namespaces
            
            return epub.write_epub(output_file, new_book)
        
        except Exception as e:
            import traceback
            print(f"An ERROR occurred while optimizing epub:")
            for line in traceback.format_exception(e):
                print(line.rstrip())
            return False


HELP = f"Usage: {Path(__file__).name} input.epub output.epub"

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(HELP)
    else:
        input_str = sys.argv[1]
        output_str = sys.argv[2]
        
        # Check input/output paths
        input_path = Path(input_str)
        output_path = Path(output_str)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file {input_path.absolute()} not found!")
        if output_path.exists():
            raise FileExistsError(f"Output file {output_path.absolute()} already exists!")

        # Do the actual epub stuff
        input_epub = ParsedEpub(epub.read_epub(input_path))
        if input_epub.export_epub(output_str):
            print(f"Successfully wrote optimized EPUB to: {output_str}")
            subprocess.run(['rm', '-r', input_epub.temp_dir])
