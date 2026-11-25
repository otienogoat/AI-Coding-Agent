
import threading

import tiktoken

# tiktoken downloads its BPE file on first use and blocks indefinitely when the
# download is unavailable. Load it on a daemon thread with a timeout so callers
# can fall back to estimate_tokens() instead of hanging the agent.
_TOKENIZERS:dict[str,object|None]={}
_LOAD_TIMEOUT=5.0


def _load_encoding(name:str):
    loaded:list[object]=[]

    def _load()->None:
        try:
            loaded.append(tiktoken.get_encoding(name))
        except Exception:
            pass

    thread=threading.Thread(target=_load,daemon=True)
    thread.start()
    thread.join(_LOAD_TIMEOUT)
    return loaded[0] if loaded else None


def get_tokenizer(model:str):
    if model in _TOKENIZERS:
        return _TOKENIZERS[model]

    try:
        encoding_name=tiktoken.encoding_name_for_model(model)
    except Exception:
        encoding_name="cl100k_base"

    encoding=_load_encoding(encoding_name)
    encode=encoding.encode if encoding is not None else None
    _TOKENIZERS[model]=encode
    return encode

def count_tokens(text:str,model:str="cl100k_base")->int:
    tokenizer=get_tokenizer(model)

    if tokenizer:
        return len(tokenizer(text))
    return estimate_tokens(text)


def estimate_tokens(text:str)->int:
    return max(1,len(text) // 4)

def truncate_text(
        text:str,
        model:str,
        max_tokens:int,
        suffix:str="\n...[truncated]",
        preserve_lines:bool=True,):
    current_tokens=count_tokens(text,model)
    if current_tokens<=max_tokens:
        return text

    suffix_tokens=count_tokens(
        suffix,model
    )
    target_tokens=max_tokens-suffix_tokens

    if target_tokens <=0:
        return suffix.strip()
    if preserve_lines:
        return _truncate_by_lines(text,target_tokens,suffix,model)
    else:
        return _truncate_by_chars(text,target_tokens,suffix,model)
    
def _truncate_by_lines(text:str,target_tokens:int,suffix:str,model:str):
    """Truncate text at line boundaries."""
    lines=text.split("\n")
    result_lines:list[str]=[]
    current_tokens=0

    for line in lines:
        line_tokens=count_tokens(line + "\n",model)

        if current_tokens + line_tokens >target_tokens:
            break
        result_lines.append(line)
        current_tokens +=line_tokens

    if not result_lines:
        #Fall back to character truncation if no complete lines
        return _truncate_by_chars(text,target_tokens,suffix,model)
    return "\n".join(result_lines) + suffix

def _truncate_by_chars(text:str,target_tokens:int,suffix:str,model:str):
    """Binary search for the right length."""
    low,high =0,len(text)

    while low <high:
        mid =(low + high + 1)//2
        if count_tokens(text [:mid],model)<=target_tokens:
            low=mid

        else:
            high=mid-1

    return text[:low]+suffix


    



    