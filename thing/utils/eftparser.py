# The MIT License (MIT)
# 
# Copyright (c) 2013 Guillaume - https://github.com/Kyria/EFTParser
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 


class EFTParser(object):

    
    @staticmethod
    def parse(eft_textblock):
        """
        Parse an EFT Text Block and return an usable structure.
        
        {   
            ship_type: xx,
            fit_name: xx,
            modules: [
                {name: xxx, charge: yyy},
                ...
            ],
            cargodrones: [
                {name: xxx, quantity: yyy},
            ]
        }
        """
    
            
        fit_lines = eft_textblock.strip().splitlines()
        
        module_list      = []
        cargodrone_list  = []
        ship_type        = ''
        fit_name         = ''

        for line in fit_lines:
            # we start with stripping white spaces
            line = line.strip()
                
            # is the line empty ?
            if len(line) == 0:
                continue
                
            # does the line start with brackets ?
            if line[0] == '[':
            
                # is the line an empty slot ?
                if line[1:-1].lower() in {'empty low slot', 'empty med slot', 'empty high slot', 'empty rig slot', 'empty subsystem slot'}:
                    continue
                
                # it must be the ship type 
                if line.find(",") > 0:
                   ship_type, fit_name = line[1:-1].split(', ')
                
                

            # it does not start with brackets
            else:
                
                # does the module have any charges
                if line.find(",") > 0:
                    module, charge = line.split(',')
                    module_list.append({"name": module.strip(), "charge": charge.strip()})
             
                # module without charge or drone/ammunition
                else:
                    quantity = line.split()[-1]
                    
                    # if it is a quantity; it's just a drone / ammo
                    if quantity[0] == 'x' and quantity[1:].isdigit():
                        charge_name = " ".join(line.split()[:-1]).strip()
                        quantity    = int(quantity[1:])
                        
                        cargodrone_list.append({"name": charge_name, "quantity": quantity})
                    
                    else:
                        module_list.append({"name": line.strip(), "charge": ''})


        result = {"ship_type": ship_type, "fit_name": fit_name, "modules": module_list, "cargodrones": cargodrone_list}
        return result
