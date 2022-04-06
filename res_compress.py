import os
import shutil
import sys
import distutils.spawn

#######  change theses params to tune compression output #######

CONST_OUTPUT_QUALITY_PNGQUANT = '95'
CONST_OUTPUT_QUALITY_CWEBP = '90'

################################################################

CONST_EXEC_PNGQUANT = 'pngquant'
CONST_EXEC_CWEBP = 'cwebp'
CONST_DIR_RES = 'res'
CONST_DIR_BUILD = 'build'
CONST_EXT_PNG = 'png'
CONST_EXT_WEBP = 'webp'
CONST_SUFFIX_BACKUP = '_ORIGINAL_BACKUP'
CONST_SUFFIX_COMPRESSED = '_COMPRESSED'

STATUS_COMPRESSED = 0
STATUS_SKIPPED = 1
STATUS_ERROR = 2

FILES_STATUS = {}
FILES_SIZES_ORIGINAL = {}
FILES_SIZES_COMPRESSED = {}

VERBOSE_LOG_ENABLED = False

counter_total = 0
counter_current = 0


def remove_file(file):
    try:
        os.remove(file)
    except FileNotFoundError:
        pass


def ensure_dir_exist(dir):
    if not (os.path.exists(dir) and os.path.isdir(dir)):
        print("Invalid path provided")
        sys.exit(-1)


def ensure_tool_binary_exist(binary, name):
    if binary is None:
        print("Missing external binary in path: %s. Please install it before running this script" % name)
        sys.exit(-1)


def ensure_tools_binaries_exist():
    pngquant = distutils.spawn.find_executable(CONST_EXEC_PNGQUANT)
    ensure_tool_binary_exist(pngquant, CONST_EXEC_PNGQUANT)
    cwebp = distutils.spawn.find_executable(CONST_EXEC_CWEBP)
    ensure_tool_binary_exist(cwebp, CONST_EXEC_CWEBP)


# todo paths for windows ??

def find_png_img_resources(dir):
    all_files = []
    for root, subdirs, files in os.walk(dir):
        all_files += [os.path.join(root, file) for file in files]
    files_not_in_build = list(filter(lambda f: "/%s/" % CONST_DIR_BUILD not in f, all_files))
    files_in_res = list(filter(lambda f: "/%s/" % CONST_DIR_RES in f, files_not_in_build))
    files_png_res = list(filter(lambda f: f.endswith(".%s" % CONST_EXT_PNG), files_in_res))
    files_without_suffix_backup = list(filter(lambda f: not f.endswith("%s.%s" % (CONST_SUFFIX_BACKUP, CONST_EXT_PNG)), files_png_res))
    files_without_suffix_compressed = list(filter(lambda f: not f.endswith("%s.%s" % (CONST_SUFFIX_COMPRESSED, CONST_EXT_PNG)), files_without_suffix_backup))
    return files_without_suffix_compressed


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def process_single_png_image_file(file):
    if counter_total > 0:
        current_progress = float(counter_current) / float(counter_total) * float(100)
        sys.stdout.write("Progress: %d of %d files processed (%d%%)   \r" % (counter_current, counter_total, int(current_progress)))
        sys.stdout.flush()

    orig_file = file
    orig_file_size = os.path.getsize(orig_file)
    dir_name = os.path.dirname(orig_file)
    base_name = os.path.basename(orig_file)
    name = base_name.split(".")[0]
    ext = base_name.split(".")[-1]

    backup_file = os.path.join(dir_name, "%s%s.%s" % (name, CONST_SUFFIX_BACKUP, ext))
    compressed_file = os.path.join(dir_name, "%s%s.%s" % (name, CONST_SUFFIX_COMPRESSED, ext))
    webp_file = os.path.join(dir_name, "%s.%s" % (name, CONST_EXT_WEBP))

    try:
        remove_file(backup_file)
        shutil.copyfile(orig_file, backup_file)

        remove_file(compressed_file)

        cmd_pngquant = "pngquant --strip --quality %s --output \"%s\" \"%s\" --force" % (CONST_OUTPUT_QUALITY_PNGQUANT, compressed_file, orig_file)
        result_pngquant = os.system(cmd_pngquant)

        if not os.path.exists(compressed_file):
            FILES_STATUS[file] = STATUS_ERROR
            FILES_SIZES_ORIGINAL[file] = orig_file_size
            FILES_SIZES_COMPRESSED[file] = orig_file_size
            remove_file(compressed_file)
            remove_file(backup_file)
            if VERBOSE_LOG_ENABLED:
                print("%s ERROR. restoring backup..." % orig_file)
            return None

        compressed_file_size = os.path.getsize(compressed_file)
        if compressed_file_size >= orig_file_size:
            FILES_STATUS[file] = STATUS_SKIPPED
            FILES_SIZES_ORIGINAL[file] = orig_file_size
            FILES_SIZES_COMPRESSED[file] = orig_file_size
            remove_file(compressed_file)
            remove_file(backup_file)
            if VERBOSE_LOG_ENABLED:
                print("%s skipped. Result compressed size is larger than original png. restoring backup..." % orig_file)
            return None


        cmd_cwebp = "cwebp -q %s \"%s\" -o \"%s\"  > /dev/null 2>&1" % (CONST_OUTPUT_QUALITY_CWEBP, compressed_file, webp_file)
        result_cwebp = os.system(cmd_cwebp)

        if not os.path.exists(webp_file):
            FILES_STATUS[file] = STATUS_ERROR
            FILES_SIZES_ORIGINAL[file] = orig_file_size
            FILES_SIZES_COMPRESSED[file] = orig_file_size
            remove_file(compressed_file)
            remove_file(backup_file)
            if VERBOSE_LOG_ENABLED:
                print("%s ERROR. restoring backup..." % orig_file)
            return None

        webp_file_size = os.path.getsize(webp_file)
        if webp_file_size < orig_file_size:
            FILES_STATUS[file] = STATUS_COMPRESSED
            FILES_SIZES_ORIGINAL[file] = orig_file_size
            FILES_SIZES_COMPRESSED[file] = compressed_file_size
            size_diff_raw = webp_file_size - orig_file_size
            size_diff_percent = (float(webp_file_size) / float(orig_file_size)) * float(100)
            if VERBOSE_LOG_ENABLED:
                print("%s compressed. Original size was %s. New size is %s. Saved %s (%.2f percents)" % (orig_file, sizeof_fmt(orig_file), sizeof_fmt(webp_file_size), sizeof_fmt(size_diff_raw), size_diff_percent))
            remove_file(compressed_file)
            remove_file(backup_file)
            remove_file(orig_file)
        else:
            FILES_STATUS[file] = STATUS_SKIPPED
            FILES_SIZES_ORIGINAL[file] = orig_file_size
            FILES_SIZES_COMPRESSED[file] = orig_file_size
            remove_file(compressed_file)
            remove_file(webp_file)
            remove_file(backup_file)
            if VERBOSE_LOG_ENABLED:
                print("%s skipped. Result webp size is larger than original png. restoring backup..." % orig_file)
    except:
        FILES_STATUS[file] = STATUS_ERROR
        FILES_SIZES_ORIGINAL[file] = orig_file_size
        FILES_SIZES_COMPRESSED[file] = orig_file_size
        remove_file(compressed_file)
        remove_file(backup_file)
        remove_file(webp_file)
        if VERBOSE_LOG_ENABLED:
            print("%s ERROR. restoring backup..." % orig_file)
        return None


def print_results():
    files_processed = len(FILES_STATUS)
    files_compressed = list(filter(lambda f: FILES_STATUS[f] == STATUS_COMPRESSED, FILES_STATUS))
    files_skipped = list(filter(lambda f: FILES_STATUS[f] == STATUS_SKIPPED, FILES_STATUS))
    files_error = list(filter(lambda f: FILES_STATUS[f] == STATUS_ERROR, FILES_STATUS))

    size_original_total = sum(FILES_SIZES_ORIGINAL.values())
    size_compressed_total = sum(FILES_SIZES_COMPRESSED.values())
    size_diff = size_original_total - size_compressed_total
    size_diff_str = sizeof_fmt(size_diff)
    if size_original_total > 0:
        size_diff_percents_str = "%.2f" % (float(size_compressed_total - size_original_total) / float(size_original_total) * float(100))
    else:
        size_diff_percents_str = "0.00"

    print(" ")
    print(" ")
    print("Result:")
    print("%d files processed" % files_processed)
    print("%d files compressed" % len(files_compressed))
    print("%s files skipped" % len(files_skipped))
    print("%s files errors during compression" % len(files_error))
    print(" ")
    print("%s space saved (%s%%)" % (size_diff_str, size_diff_percents_str))


if __name__ == '__main__':
    if len(sys.argv) == 2:
        ensure_tools_binaries_exist()
        working_dir_str = sys.argv[1]
        ensure_dir_exist(working_dir_str)
        working_dir = os.path.abspath(working_dir_str)

        png_image_resources = find_png_img_resources(working_dir)

        all_files_size_original = 0
        for file in png_image_resources:
            all_files_size_original += os.path.getsize(file)
        files_count = len(png_image_resources)
        counter_total = files_count
        print("%d png image resource files found. Total size is %s" % (files_count, sizeof_fmt(all_files_size_original)))
        print(" ")

        counter_current = 0
        for file in png_image_resources:
            counter_current += 1
            process_single_png_image_file(file)

        print_results()
    else:
        print("No path provided. Please provide root of the project as an argument to run the script")
        sys.exit(-1)
