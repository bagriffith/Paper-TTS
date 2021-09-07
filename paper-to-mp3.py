from google.cloud import texttospeech
import sys
import os
import re
import eyed3


unicode = {0xfb00: 'ff',
           0xfb01: 'fi',
           0xfb02: 'fl',
           0xfb03: 'ffi',
           0xfb04: 'ffl',
           0x226A: 'is much less than',
           0x226B: 'is much greater than'}


def add_chapters(filename, chaps, times):
    audioFile = eyed3.core.load(filename)
    tag = eyed3.id3.Tag()
    tag.parse(filename)
    total_length = audioFile.info.time_secs * 1000
    tag.setTextFrame(b"TLEN", str(int(total_length)))

    chap_bounds = []
    child_ids = []
    for i, (c, t) in enumerate(zip(chaps, times)):
        if len(chap_bounds) == 0:
            times = (0, t * 1000)
        else:
            times = (chap_bounds[-1][-1], chap_bounds[-1][-1]+t * 1000)
        chap_bounds.append(times)
        element_id = "ch{}".format(i).encode()
        new_chap = tag.chapters.set(element_id, times)
        new_chap.sub_frames.setTextFrame(b"TIT2", u"{}".format(c))
        child_ids.append(element_id)
    tag.table_of_contents.set(b"toc", child_ids=child_ids)
    for chap in tag.chapters:
        print(chap.sub_frames.get(b"TIT2")[0]._text)
    tag.save()


def generate_audio_for_file(text_path, out_path):
    with open(text_path, mode='r') as file:
        text_block = file.read()
    
    text_block = text_block.translate(unicode)
    text_block = '\n' + text_block

    text_block_list = re.split(r'((?<=[\r\n])[\t ]*#+[ \t\f\v\S]*[\r\n])', text_block)
    text_block_list = [b.strip() for b in text_block_list if not b.isspace() and b]
    del text_block

    MAX_SIZE = 4999
    _split_on_order = ['\n\n', '.\n', '. ', ' ', None]
    for sep in _split_on_order:
        for i, text_block in enumerate(text_block_list):
            size = len(text_block)
            if size > MAX_SIZE:
                if sep is None:
                    raise RuntimeError("Couldn't divide up text to " + str(MAX_SIZE) + " char")

                text_block_list[i:i+1] = [s+sep for s in text_block.split(sep) if not s.isspace() and s]
    
    tmp_paths = [out_path + '.' + str(n) for n in range(len(text_block_list))]

    block_titles = []

    for text_block, block_out_path in zip(text_block_list, tmp_paths):
        title = re.search(r'(?<=#)[^#\n]+(?=#*.*)$', text_block)
        block_titles.append(title.group(0).strip() if title is not None else '')
        
        generate_audio_for_text(text_block if title is None else block_titles[-1],
                                block_out_path, block_titles[-1]!='')

    with open(out_path, 'wb') as f:
        None

    block_times = []
    for block_out_path in tmp_paths:
        block_times.append(eyed3.load(block_out_path).info.time_secs)
        with open(block_out_path, 'rb') as f:
            data = f.read()

        os.remove(block_out_path)

        with open(out_path, 'ab') as f:
            f.write(data)

    titles = []
    times = []
    for time, label in zip(block_times, block_titles):
        if label:
            titles.append(label)
            times.append(time)
        else:
            if times:
                times[-1] += time
    
    # print(titles)
    # print(times)
    add_chapters(out_path, titles, times)



def generate_audio_for_text(text_block, out_path, is_title=False):
    # return
    # Instantiates a client
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text_block)

    if is_title:
        voice = texttospeech.VoiceSelectionParams(language_code='en-US',
                                                  name='en-US-Wavenet-B')
        speed = 1.2
    else:
        voice = texttospeech.VoiceSelectionParams(language_code='en-US',
                                                  name='en-US-Wavenet-J')
        speed = 1.5

    # Select the type of audio file you want returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speed,
        effects_profile_id=['headphone-class-device']
    )

    # Perform the text-to-speech request on the text input with the selected
    # voice parameters and audio file type
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # The response's audio_content is binary.
    with open(out_path, "wb") as out:
        # Write the response to the output file.
        out.write(response.audio_content)
        print('Audio content written to file', out_path)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise ValueError('Must be run as "paper-to-mp3.py "')
    
    text_file = sys.argv[1]
    out_file = sys.argv[2]
    generate_audio_for_file(text_file, out_file)
