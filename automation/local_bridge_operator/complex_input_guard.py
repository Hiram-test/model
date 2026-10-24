import argparse,json,math,re # Reject native numeric-field truncation before a nonlinear solve can produce misleading labels.
from pathlib import Path # Support direct checks of generated CalculiX inputs.
NUMBER=re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?$') # Recognize actual numeric fields without mistaking material or set names for numbers.
def validate_numeric_fields(text,limit=20): # Enforce the verified native numeric-field width without changing the physical input.
    issues=[];count=0 # Preserve exact line and field ownership for every rejected input.
    for line_number,line in enumerate(text.splitlines(),1): # Inspect all generated data cards in their original order.
        stripped=line.strip() # Normalize only surrounding whitespace for field-length checks.
        if not stripped or stripped.startswith('*'): continue # Leave native keywords and comment records outside the numeric-data scan.
        for field_number,field in enumerate(line.split(','),1): # Match native comma-separated data-card fields.
            token=field.strip() # Preserve the token itself for a reproducible failure record.
            if not NUMBER.fullmatch(token): continue # Do not reinterpret textual headers or named node and element sets.
            count+=1;value=float(token.replace('D','E').replace('d','e')) # Parse the intended numeric value independently of the native fixed-width reader.
            if len(token)>limit or not math.isfinite(value): issues.append({'line':line_number,'field':field_number,'token':token,'characters':len(token),'reason':'numeric field exceeds native width' if len(token)>limit else 'nonfinite numeric value'}) # Fail before an exponent can be silently shortened.
    if issues: raise ValueError(json.dumps({'status':'REJECTED_NATIVE_NUMERIC_INPUT','numeric_fields_checked':count,'issues':issues},ensure_ascii=False)) # Keep malformed inputs separate from numerical or structural failures.
    return {'status':'PASS','numeric_fields_checked':count,'maximum_allowed_characters':limit} # Report only syntax safety, never imply geometric or mechanical validity.
def scientific(value): # Format native floating-point data safely without dropping tiny signed coordinates.
    result=f'{float(value):.12e}';assert len(result)<=20 and math.isfinite(float(value));return result # Preserve the exponent within the native field width.
def self_check(): # Reproduce the discovered exponent-truncation failure and its safe encoding.
    bad='-7.82722300202892e-16';good=scientific(float(bad));rejected=False # Use the actual problematic numeric form instead of a synthetic unrelated test.
    try: validate_numeric_fields('*NODE\n1,'+bad+',0.,0.\n') # Verify rejection before a malformed native coordinate reaches the solver.
    except ValueError: rejected=True # Confirm that the guard closes the identified failure path.
    accepted=validate_numeric_fields('*NODE\n1,'+good+',0.,0.\n');assert rejected and abs(float(good)-float(bad))<1.e-27;return {'bad_field_rejected':rejected,'safe_field':good,'preserved_coordinate_mm':float(good),'would_be_truncated_value_mm':float(bad[:20]),'safe_input_check':accepted} # Show why an apparently tiny coordinate became a millimetre-scale defect.
if __name__=='__main__': # Expose both the meaningful regression check and explicit native-input validation.
    parser=argparse.ArgumentParser();parser.add_argument('input',nargs='?');args=parser.parse_args();print(json.dumps(validate_numeric_fields(Path(args.input).read_text()) if args.input else self_check(),ensure_ascii=False,indent=2)) # Avoid modifying an input or masking a failing validation.
