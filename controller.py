from automation_inbloom import rocket_luncher_inbloom
# from automation_abc import rocket_luncher_inbloom
# from automation_v2 import part1_part2_runner

def rocket_luncher(data):
    if data['companyId'] == '02691328-b72f-45fa-8092-f1be06ab5384':  # inBloom
        print("***** InBloom COMPANY")
        print("Input Data For InBloom : ", data)
        res = rocket_luncher_inbloom(data)
        print("Returned Data For InBloom : ", res)
        return res
    # if data['companyId'] == 'b0838d3d-2b6d-4c82-9dc1-b75a48e4f451':  # change to blue_sprig branch id
    #     print("***** BLUE SPRIG COMPANY")
    #     #return rocket_luncher_blue_sprig(data)
    # if data['companyId'] == '5bc531ab-611f-41f3-9373-b7cc5d09c93d':  # change to abc branch id
    #     print("***** ABC COMPANY")
    #     #return rocket_luncher_abc(data)
    else: 
        return rocket_luncher_inbloom(data)
