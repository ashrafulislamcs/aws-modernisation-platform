package test

import (
    "encoding/json"
	"testing"
	"regexp"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
)

func TestTransitGateway(t *testing.T) {
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: "../",
	})

	terraform.RunTerraformCommand(t, terraformOptions, "refresh")
	terraform.Plan(t, terraformOptions)

	//Test transit-gateway will not be affected
	output2 := terraform.Output(t, terraformOptions, "transit_gateway")
	assert.Equal(t, output2, "64589")

	//Check the transit gateway ram share is created
	output6 := terraform.Output(t, terraformOptions, "transit_gateway_ram_share")
	assert.Equal(t, output6, "transit-gateway")

}

func TestInspectionVPCs(t *testing.T) {
	terraformOptions := terraform.WithDefaultRetryableErrors(t, &terraform.Options{
		TerraformDir: "../",
	})

	terraform.RunTerraformCommand(t, terraformOptions, "refresh")
	terraform.Plan(t, terraformOptions)

	// Retrieve the VPC output as a map
	vpcIDs := terraform.OutputMap(t, terraformOptions, "inspection_vpc_ids")

	// Define a regular expression pattern to match the VPC IDs
	vpcIDPattern := regexp.MustCompile(`^vpc-[0-9a-f]{17}$`)

	// Assert that the vpc_id values in the map match the regular expression pattern
	assert.Regexp(t, vpcIDPattern, vpcIDs["non_live_data"], "non_live_data vpc_id does not match the expected pattern")
	assert.Regexp(t, vpcIDPattern, vpcIDs["live_data"], "live_data vpc_id does not match the expected pattern")

	// Retrieve the subnet outputs
	tgwSubnets := terraform.OutputMap(t, terraformOptions, "inspection_tgw_subnets")
	inspectionSubnets := terraform.OutputMap(t, terraformOptions, "inspection_inspection_subnets")
	publicSubnets := terraform.OutputMap(t, terraformOptions, "inspection_public_subnets")

	// Assert that non_live_data has all of its subnets
	assert.Equal(t, tgwSubnets["non_live_data"], "3")
	assert.Equal(t, inspectionSubnets["non_live_data"], "3")
	assert.Equal(t, publicSubnets["non_live_data"], "3")

	// Assert that live_data has all of its subnets
	assert.Equal(t, tgwSubnets["live_data"], "3")
	assert.Equal(t, inspectionSubnets["live_data"], "3")
	assert.Equal(t, publicSubnets["live_data"], "3")

	// Retrieve firewall ARNs as a map
	firewallARNs := terraform.OutputMap(t, terraformOptions, "firewall_arn")
	// Define a regular expression pattern to match the VPC IDs
	firewallARNPattern := regexp.MustCompile(`^arn:aws:network-firewall:eu-west-2:[0-9]{12}:firewall/(live-data|non-live-data)-inline-inspection$`)
	// Assert that the firewall_arn values in the map match the regular expression pattern
	assert.Regexp(t, firewallARNPattern, firewallARNs["non_live_data"], "non_live_data firewall_arn does not match the expected pattern")
	assert.Regexp(t, firewallARNPattern, firewallARNs["live_data"], "live_data firewall_arn does not match the expected pattern")

	// Retrieve Internet Gateway IDs
	igwIDs := terraform.OutputMap(t, terraformOptions, "inspection_igw_id")
	// Define a regular expression pattern to match the VPC IDs
	igwIDPattern := regexp.MustCompile(`^igw-[0-9a-f]{17}$`)
	// Assert that both live_data and non_live_data have an IGW matching the regex
	assert.Regexp(t, igwIDPattern, igwIDs["non_live_data"], "non_live_data igw_id does not match the expected pattern")
	assert.Regexp(t, igwIDPattern, igwIDs["live_data"], "live_data igw_id does not match the expected pattern")

	// Retrieve a map of NAT Gateway outputs
	natGWs := terraform.OutputMap(t, terraformOptions, "inspection_natgw_ids")

	// Assert that each VPC has all of its NAT Gateways
	assert.Equal(t, natGWs["non_live_data"], "3")
	assert.Equal(t, natGWs["non_live_data"], "3")

	// Run `terraform output` to get the value of the output variable as a string
	terraformOutput := terraform.OutputJson(t, terraformOptions, "inspection_default_routes")

	// Parse the string value as JSON to obtain the map structure
	var defaultRoutes map[string]interface{}
	err := json.Unmarshal([]byte(terraformOutput), &defaultRoutes)
	if err != nil {
		t.Fatalf("Failed to parse inspection_default_routes output as JSON: %s", err)
	}

	// Check the number of keys in `inspection_default_routes`
	liveDataRoutes, _ := defaultRoutes["live_data"].(map[string]interface{})
	nonLiveDataRoutes, _ := defaultRoutes["non_live_data"].(map[string]interface{})

	assert.Len(t, liveDataRoutes, 9)
	assert.Len(t, nonLiveDataRoutes, 9)

	// Check the values of the keys in `inspection_default_routes`
	for _, value := range liveDataRoutes {
		assert.Equal(t, "0.0.0.0/0", value)
	}
	for _, value := range nonLiveDataRoutes {
		assert.Equal(t, "0.0.0.0/0", value)
	}
}